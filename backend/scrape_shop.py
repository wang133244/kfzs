"""抓取淘宝店铺所有商品并写入橱窗。依赖 OpenCLI + 已登录 Edge。"""
import asyncio, json, re, sys, shutil
from pathlib import Path

SHOP_URL = "https://shop573231636.taobao.com/category.htm?spm=a21n57.shop_search.0.0.35293bb3Fnx0ag"
SESSION = "crawl"
OUT_FILE = Path(__file__).parent / "scraped_products.json"

def _find_opencli() -> str:
    p = shutil.which("opencli")
    if p:
        return p
    for candidate in [
        Path.home() / "AppData/Roaming/npm/opencli.cmd",
        Path.home() / "AppData/Roaming/npm/opencli",
    ]:
        if candidate.exists():
            return str(candidate)
    return "opencli"

OPENCLI = _find_opencli()

async def run_opencli(*args: str) -> str:
    proc = await asyncio.create_subprocess_exec(OPENCLI, *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await proc.communicate()
    out = stdout.decode(errors="replace").strip()
    err = stderr.decode(errors="replace").strip()
    if proc.returncode != 0:
        if out:
            return out
        raise RuntimeError(f"opencli failed ({proc.returncode}): {err or out}")
    return out

def parse_json(raw):
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        pass
    try:
        env = json.loads(raw)
        if isinstance(env, dict):
            for k in ("result", "data", "value", "output"):
                v = env.get(k)
                if isinstance(v, str):
                    try:
                        return json.loads(v)
                    except json.JSONDecodeError:
                        continue
                if isinstance(v, (dict, list)):
                    return v
    except (json.JSONDecodeError, TypeError):
        pass
    return None

SCROLL_JS = "() => { window.scrollTo(0, document.body.scrollHeight); return String(document.body.scrollHeight); }"

EXTRACT_JS = (
    "(() => {"
    "  var links = [].slice.call(document.querySelectorAll('a[href*=\"item.taobao\"], a[href*=\"detail.tmall\"]'));"
    "  var items = [], seen = {};"
    "  links.forEach(function(a) {"
    "    var href = a.href || ''; if (!href) return;"
    "    var id = ''; try { id = new URL(href, location.origin).searchParams.get('id') || ''; } catch(e) {}"
    "    if (!id || seen[id]) return; seen[id] = 1;"
    "    var c = a;"
    "    for (var i = 0; i < 8; i++) {"
    "      if (c.parentElement) c = c.parentElement;"
    "      var imgs = c.querySelectorAll('img');"
    "      var prices = c.querySelectorAll('[class*=\"price\"], [class*=\"Price\"], [data-price]');"
    "      if (imgs.length > 0 && prices.length > 0) break;"
    "    }"
    "    var title = (a.getAttribute('title') || a.textContent || '').trim().slice(0, 120);"
    "    var priceText = '';"
    "    var pels = c.querySelectorAll('[class*=\"price\"], [class*=\"Price\"], [data-price]');"
    "    for (var j = 0; j < pels.length; j++) {"
    "      var m = (pels[j].textContent || '').match(/(\\d+(?:\\.\\d+)?)/);"
    "      if (m && parseFloat(m[1]) > 0) { priceText = m[1]; break; }"
    "    }"
    "    var img = c.querySelector('img');"
    "    var imgSrc = '';"
    "    if (img) imgSrc = img.src || img.getAttribute('data-ks-lazyload') || img.getAttribute('data-src') || '';"
    "    var salesText = '';"
    "    var sels = c.querySelectorAll('[class*=\"sale\"], [class*=\"Sale\"], [class*=\"sold\"], [class*=\"deal\"]');"
    "    for (var k = 0; k < sels.length; k++) {"
    "      var m2 = (sels[k].textContent || '').match(/(\\d+(?:\\.\\d+)?)/);"
    "      if (m2 && parseInt(m2[1]) > 0) { salesText = m2[1]; break; }"
    "    }"
    "    if (title.length > 2) items.push({ id: id, title: title, price: parseFloat(priceText) || 0, image: imgSrc, link: href, sales: parseInt(salesText) || 0 });"
    "  });"
    "  return JSON.stringify({ count: items.length, items: items.slice(0, 80) });"
    "})()"
)

async def main():
    # Step 1: open shop (skip if already open)
    print("[1/4] checking current page...")
    info = {}
    try:
        raw = await asyncio.wait_for(run_opencli("browser", SESSION, "eval", "({url: location.href, title: document.title})"), timeout=10)
        info = parse_json(raw) or {}
        cur_url = str(info.get("url", ""))
        if SHOP_URL.split("?")[0] not in cur_url:
            print(f"  navigating to shop...")
            await asyncio.wait_for(run_opencli("browser", SESSION, "open", SHOP_URL), timeout=15)
            print("[2/4] wait 4s for render...")
            await asyncio.sleep(4)
        else:
            print(f"  already on shop page: {info.get('title','')}")
            print("[2/4] page ready")
    except asyncio.TimeoutError:
        print("  timeout checking page, continuing anyway...")
    except RuntimeError as e:
        print(f"  error: {e}")
    title = str(info.get("title", "")); url = str(info.get("url", ""))
    if "登录" in title or "login" in url.lower():
        print("  WARN: on login page! Please login in Edge and re-run."); sys.exit(1)
    print("[3/4] scroll to load lazy items...")
    for i in range(4):
        try:
            await asyncio.wait_for(run_opencli("browser", SESSION, "eval", SCROLL_JS), timeout=10)
        except asyncio.TimeoutError:
            print(f"  scroll {i+1} timeout, continuing...")
        await asyncio.sleep(1.5)
    print("[4/4] extract product data...")
    try:
        raw = await asyncio.wait_for(run_opencli("browser", SESSION, "eval", EXTRACT_JS), timeout=15)
    except asyncio.TimeoutError:
        print("  extract timeout, trying extract markdown...")
        raw = ""
    data = parse_json(raw) or {}
    items = data.get("items", []) if isinstance(data, dict) else []
    count = data.get("count", 0) if isinstance(data, dict) else 0
    print(f"  JS found {count} products ({len(items)} after dedup)")
    if not items:
        print("  fallback: extract markdown...")
        try:
            md = await run_opencli("browser", SESSION, "extract")
            found = re.findall(r'https?://item\.taobao\.com/item\.htm\?id=(\d+)', md)
            print(f"  found {len(set(found))} ids in markdown")
            for fid in list(dict.fromkeys(found))[:80]:
                items.append({"id": fid, "title": "", "price": 0, "image": "", "link": f"https://item.taobao.com/item.htm?id={fid}", "sales": 0})
        except RuntimeError as e:
            print(f"  extract failed: {e}")
    OUT_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nOK saved {len(items)} products to {OUT_FILE}")
    for i, it in enumerate(items[:10]):
        print(f"  [{i+1}] {it['title'][:40]}  Y{it.get('price',0)}  {it.get('image','')[:50]}")
    if len(items) > 10:
        print(f"  ... {len(items)-10} more")

if __name__ == "__main__":
    asyncio.run(main())
