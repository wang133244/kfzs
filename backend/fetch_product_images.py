"""逐个访问商品详情页，提取 og:image 并更新数据库。"""
import asyncio, json, sys, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from scrape_shop import run_opencli, parse_json, SESSION, OUT_FILE
from app.core.product_service import reload_memory
from app.db import async_session_factory
from app.models import Product
from sqlalchemy import select
OG_JS = '(() => { var el = document.querySelector("meta[property=\"og:image\"], meta[name=\"og:image\"]"); return el ? el.content : ""; })()'
FALLBACK_JS = '(() => { var imgs = document.querySelectorAll("img"); for (var i=0;i<imgs.length;i++) { var s = imgs[i].src; if (s && s.indexOf("alicdn")>-1 && s.indexOf("logo")<0) return s; } return ""; })()'
async def fetch_image(url):
    try:
        await asyncio.wait_for(run_opencli("browser", SESSION, "open", url, "--window", "background"), timeout=15)
    except Exception:
        pass
    await asyncio.sleep(3)
    try:
        raw = await asyncio.wait_for(run_opencli("browser", SESSION, "eval", OG_JS), timeout=10)
        img = parse_json(raw)
        if isinstance(img, str) and img:
            return img
    except Exception:
        pass
    try:
        raw2 = await run_opencli("browser", SESSION, "eval", FALLBACK_JS)
        return parse_json(raw2) or ""
    except Exception:
        return ""
async def main():
    products = json.loads(OUT_FILE.read_text(encoding="utf-8"))
    print(f"Fetching images for {len(products)} products...\n")
    img_map = {}
    for i, p in enumerate(products):
        link = p.get("link", "")
        pid = p.get("id", "")
        print(f"[{i+1}/{len(products)}] {pid} ...", end=" ", flush=True)
        img = await fetch_image(link)
        img_map[pid] = img
        print(img[:60] if img else "NO IMAGE")
    print("\nUpdating database...")
    updated = 0
    async with async_session_factory() as session:
        result = await session.scalars(select(Product).where(Product.source_url.contains("item.taobao")))
        for p in result:
            for pid, img in img_map.items():
                if pid and pid in (p.source_url or "") and img:
                    p.cover = img
                    p.gallery_json = json.dumps([img], ensure_ascii=False)
                    updated += 1
                    print(f"  {p.product_id}: {img[:60]}")
                    break
        await session.commit()
    await reload_memory()
    print(f"\nDone: {updated} products updated with images")
if __name__ == "__main__":
    asyncio.run(main())
