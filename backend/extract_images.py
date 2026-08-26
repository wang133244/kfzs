"""从店铺页面提取每个商品的图片，更新数据库。"""
import asyncio, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from scrape_shop import run_opencli, parse_json, SESSION
from app.core.product_service import reload_memory
from app.db import async_session_factory
from app.models import Product
from sqlalchemy import select
IMG_JS = '(() => { var links = [].slice.call(document.querySelectorAll("a[href*=\"item.taobao\"]")); var result = [], seen = {}; links.forEach(function(a) { var href = a.href || ""; if (!href) return; var id = ""; try { id = new URL(href, location.origin).searchParams.get("id") || ""; } catch(e) {} if (!id || seen[id]) return; seen[id] = 1; var c = a; for (var i = 0; i < 8; i++) { if (c.parentElement) c = c.parentElement; if (c.querySelectorAll("img").length > 0) break; } var imgs = c.querySelectorAll("img"); var imgSrc = ""; for (var j = 0; j < imgs.length; j++) { var s = imgs[j].src || imgs[j].getAttribute("data-ks-lazyload") || imgs[j].getAttribute("data-src") || ""; if (s && s.indexOf("alicdn") > -1 && s.indexOf("tps-2-2") < 0 && s.indexOf("logo") < 0) { imgSrc = s; break; } } result.push({ id: id, image: imgSrc }); }); return JSON.stringify(result); })()'
async def main():
    print("Extracting images from shop page...")
    raw = await asyncio.wait_for(run_opencli("browser", SESSION, "eval", IMG_JS), timeout=15)
    imgs = parse_json(raw) or []
    print(f"Got {len(imgs)} image entries")
    img_map = {item["id"]: item.get("image", "") for item in imgs if isinstance(item, dict)}
    for pid, url in list(img_map.items())[:5]:
        print(f"  {pid}: {url[:60]}")
    print("\nUpdating database...")
    updated = 0
    async with async_session_factory() as session:
        result = await session.scalars(select(Product).where(Product.source_url.contains("item.taobao")))
        for p in result:
            img = ""
            for pid2, url2 in img_map.items():
                if pid2 and pid2 in (p.source_url or ""):
                    img = url2
                    break
            if img:
                p.cover = img
                p.gallery_json = json.dumps([img], ensure_ascii=False)
                updated += 1
                print(f"  {p.product_id}: {img[:50]}")
        await session.commit()
    await reload_memory()
    print(f"\nUpdated {updated} products with images")
if __name__ == "__main__":
    asyncio.run(main())
