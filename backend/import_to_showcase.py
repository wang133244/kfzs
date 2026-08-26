"""读取 scraped_products.json，清理数据后通过 product_service 添加到橱窗。"""
import asyncio, json, re, sys, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from app.seed import init_db
from app.core.product_service import create_product

DATA_FILE = Path(__file__).parent / "scraped_products.json"
CATEGORY = "柱头灯"
CATEGORY_CODE = "post"

def clean_title(raw):
    for marker in ["¥", "中国大陆", "≤36V", "人付款", "24小时"]:
        idx = raw.find(marker)
        if idx > 0:
            raw = raw[:idx]
    return raw.strip()

def extract_price_sales(raw):
    m = re.search(r"[¥￥](\d+(?:\.\d+)?)", raw)
    if not m:
        return 0.0, 0
    num = float(m.group(1))
    # 如果数字 > 500，末尾 1 位是销量，前面是价格
    if num > 500 and len(m.group(1)) > 2:
        price_str = m.group(1)[:-1]
        sales = int(m.group(1)[-1])
        return float(price_str), sales
    return num, 0

async def main():
    if not DATA_FILE.exists():
        print(f"ERROR: {DATA_FILE} not found. Run scrape_shop.py first.")
        sys.exit(1)
    # 初始化数据库（建表 + 种子数据 + 内存同步）
    print("Initializing database...")
    await init_db()
    print("Database ready.\n")

    products = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    print(f"Loaded {len(products)} scraped products\n")
    added = 0
    for i, p in enumerate(products):
        raw_title = p.get("title", "")
        title = clean_title(raw_title)
        price, sales = extract_price_sales(raw_title)
        link = p.get("link", "")
        image = p.get("image", "")
        if len(title) < 3:
            title = f"商品{i+1}"
        if "tps-2-2" in image or not image:
            image = ""
        print(f"[{i+1}/{len(products)}] {title[:40]}  Y{price}  sales={sales}")
        try:
            result = await create_product({
                "title": title,
                "subtitle": "星途户外照明",
                "category": CATEGORY,
                "category_code": CATEGORY_CODE,
                "price": price,
                "original_price": price,
                "sales_count": sales,
                "cover": image,
                "cover_color": "#FDE68A",
                "description": f"来源: {link}",
                "gallery": [image] if image else [],
                "specs": [],
                "skus": [],
                "services": ["7天无理由退换", "全国包邮"],
                "tags": ["太阳能", "户外照明"],
                "status": "on_sale",
                "source_url": link,
            })
            print(f"  -> {result['product_id']} added")
            added += 1
        except Exception as e:
            print(f"  -> FAILED: {e}")
    print(f"\nDone: {added}/{len(products)} products added to showcase")

if __name__ == "__main__":
    asyncio.run(main())
