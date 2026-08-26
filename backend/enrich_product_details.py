"""从淘宝商品详情页补全橱窗灯具：图集、价格、参数、介绍。跳过非灯具商品。"""
import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from scrape_shop import SESSION, parse_json, run_opencli
from sqlalchemy import select

from app.core.product_service import reload_memory, update_product_fields
from app.db import async_session_factory
from app.models import Product, ProductInventory

LIGHT_HINTS = ("灯", "照明", "柱头", "壁灯", "庭院")

DETAIL_JS = r"""
(() => {
  const meta = (p) => {
    const el = document.querySelector('meta[property="'+p+'"], meta[name="'+p+'"]');
    return el && el.content ? el.content.trim() : "";
  };
  const seller = "2219633788713";
  const skip = /icon|logo|sprite|avatar|favicon|tps-|qrcode|g\.alicdn|tb-logo/i;
  const urls = [];
  const add = (s) => {
    if (!s) return;
    String(s).split(/[\s,]+/).forEach((part) => {
      const m = part.match(/https?:\/\/[^\s"')]+/i);
      if (m) urls.push(m[0]);
    });
  };
  add(meta("og:image"));
  document.querySelectorAll("img").forEach((el) => {
    add(el.src);
    add(el.getAttribute("data-src"));
    add(el.getAttribute("data-ks-lazyload"));
  });
  const gallery = [...new Set(urls)].filter((s) => s.indexOf(seller) > -1 && !skip.test(s)).slice(0, 16);
  const title = (meta("og:title") || document.title || "").replace(/[-_].{0,12}淘宝.*/, "").trim();
  let priceText = "";
  const body = document.body ? document.body.innerText.slice(0, 2500) : "";
  const pm = body.match(/[¥￥]\s*(\d+(?:\.\d+)?)/);
  if (pm) priceText = pm[1];
  return JSON.stringify({ title: title, ogImage: meta("og:image"), description: meta("og:description") || "", priceText: priceText, gallery: gallery, imgCount: document.images.length });
})()
"""


def is_product_image(url: str) -> bool:
    if not url or "-tps-" in url or "tps-" in url:
        return False
    if "2219633788713" in url:
        return True
    if "imgextra" in url and re.search(r"\.(jpg|jpeg|webp)(?:$|[_.])", url, re.I):
        return True
    return False


def upgrade_image(url: str) -> str:
    if not url:
        return ""
    url = url.split("?")[0]
    url = re.sub(r"_\d+x\d+\.(jpg|png|webp)$", r".\1", url, flags=re.I)
    url = re.sub(r"\.jpg_q\d+\.jpg_\.webp$", ".jpg", url, flags=re.I)
    url = re.sub(r"\.jpg_\.webp$", ".jpg", url, flags=re.I)
    return url


def parse_price(text: str) -> float:
    if not text:
        return 0.0
    m = re.search(r"(\d+(?:\.\d+)?)", str(text).replace(",", ""))
    if not m:
        return 0.0
    value = float(m.group(1))
    if value > 100000:
        return 0.0
    return value


def is_light(product: Product) -> bool:
    blob = f"{product.title} {product.subtitle} {product.category}"
    return any(hint in blob for hint in LIGHT_HINTS)


def specs_from_title(title: str) -> list[dict]:
    specs: list[dict] = []
    if "太阳能" in title:
        specs.append({"label": "供电方式", "value": "太阳能"})
    if "LED" in title.upper() or "led" in title:
        specs.append({"label": "光源", "value": "LED"})
    if "防水" in title:
        specs.append({"label": "防护", "value": "户外防水"})
    if "≤36V" in title or "36V" in title:
        specs.append({"label": "电压", "value": "≤36V"})
    if "新中式" in title:
        specs.append({"label": "风格", "value": "新中式"})
    elif "中式" in title:
        specs.append({"label": "风格", "value": "中式"})
    elif "现代" in title:
        specs.append({"label": "风格", "value": "现代简约"})
    if "壁灯" in title:
        specs.append({"label": "安装", "value": "壁挂"})
    elif "柱头" in title:
        specs.append({"label": "安装", "value": "柱头/围墙"})
    return specs[:8]


def item_url(source_url: str) -> str:
    m = re.search(r"id=(\d+)", source_url or "")
    if not m:
        return source_url
    return f"https://item.taobao.com/item.htm?id={m.group(1)}"


async def fetch_detail(url: str) -> dict:
    try:
        await asyncio.wait_for(
            run_opencli("browser", SESSION, "open", url, "--window", "background"),
            timeout=20,
        )
    except Exception as exc:
        return {"error": str(exc)}
    await asyncio.sleep(4)
    for _ in range(3):
        try:
            await asyncio.wait_for(
                run_opencli(
                    "browser",
                    SESSION,
                    "eval",
                    "() => { window.scrollBy(0, Math.floor(window.innerHeight * 0.9)); return String(window.scrollY); }",
                ),
                timeout=8,
            )
        except Exception:
            break
        await asyncio.sleep(1.2)
    raw = ""
    try:
        raw = await asyncio.wait_for(run_opencli("browser", SESSION, "eval", DETAIL_JS), timeout=15)
    except Exception:
        raw = ""
    data = parse_json(raw)
    if not isinstance(data, dict):
        data = {}
    if len(data.get("gallery") or []) < 2:
        try:
            md = await asyncio.wait_for(run_opencli("browser", SESSION, "extract"), timeout=15)
            found = re.findall(r"https?://[^)\s]+\.(?:jpg|jpeg|png|webp)", md, flags=re.I)
            extra = [
                upgrade_image(u)
                for u in found
                if is_product_image(u)
            ]
            gallery = list(dict.fromkeys([*(data.get("gallery") or []), *extra]))
            data["gallery"] = gallery[:20]
        except Exception:
            pass
    return data


async def ensure_inventory(session, product_id: str, sku: dict) -> None:
    row = await session.scalar(select(ProductInventory).where(ProductInventory.sku_id == sku["sku_id"]))
    if row is None:
        session.add(
            ProductInventory(
                sku_id=sku["sku_id"],
                product_id=product_id,
                sku_name=sku.get("spec") or product_id,
                stock=int(sku.get("stock") or 50),
                threshold=int(sku.get("threshold") or 5),
            )
        )
    else:
        row.stock = int(sku.get("stock") or row.stock)
        row.sku_name = sku.get("spec") or row.sku_name


async def main() -> None:
    async with async_session_factory() as session:
        products = list(await session.scalars(select(Product).order_by(Product.id)))

    targets = [
        p
        for p in products
        if "item.taobao" in (p.source_url or "") and is_light(p)
    ]
    print(f"Skip non-lighting / demo items. Enrich {len(targets)} lighting products.\n")

    for i, product in enumerate(targets, 1):
        url = item_url(product.source_url)
        print(f"[{i}/{len(targets)}] {product.product_id} {url}")
        data = await fetch_detail(url)
        if data.get("error"):
            print(f"  FAIL {data['error']}")
            continue

        gallery = []
        for src in [product.cover, data.get("ogImage"), *(data.get("gallery") or [])]:
            upgraded = upgrade_image(str(src or ""))
            if upgraded and is_product_image(upgraded) and upgraded not in gallery:
                gallery.append(upgraded)
        if not gallery and product.cover:
            gallery = [upgrade_image(product.cover)]

        title = str(data.get("title") or "").strip() or product.title
        title = re.split(r"[-_]淘宝", title)[0].strip()[:80]
        description = str(data.get("description") or "").strip()
        if not description or description.startswith("来源:"):
            description = title

        price = parse_price(data.get("priceText") or "")
        if price <= 0:
            price = float(product.price or 0)

        specs = data.get("specs") or []
        if not specs:
            specs = specs_from_title(title)

        sku = {
            "sku_id": f"SKU-{product.product_id}",
            "spec": "默认规格",
            "price": float(price),
            "stock": 50,
            "threshold": 5,
        }

        await update_product_fields(
            product.product_id,
            {
                "title": title,
                "description": description,
                "cover": gallery[0] if gallery else product.cover,
                "gallery": gallery,
                "price": price,
                "original_price": price,
                "specs": specs,
                "skus": [sku],
                "source_url": url,
            },
        )
        async with async_session_factory() as session:
            await ensure_inventory(session, product.product_id, sku)
            await session.commit()
        print(f"  title={title[:40]} price={price} images={len(gallery)} specs={len(specs)}")

    await reload_memory()
    try:
        await run_opencli("browser", SESSION, "close")
    except Exception:
        pass
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
