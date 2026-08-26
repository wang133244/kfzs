"""把店铺收成星途户外照明专卖店：删除非灯具，并按柱头灯/壁灯/太阳能归类。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import select

from app.core.product_service import reload_memory
from app.db import async_session_factory
from app.models import Product, ProductInventory, Order

LIGHT_HINTS = ("灯", "照明", "柱头", "壁灯", "庭院")


def lighting_category(title: str) -> tuple[str, str]:
    if "壁灯" in title or "壁挂" in title:
        return "户外壁灯", "wall"
    if "柱头" in title or "围墙" in title or "立柱" in title:
        return "柱头灯", "post"
    return "太阳能庭院灯", "solar"


async def main() -> None:
    deleted = 0
    updated = 0
    keep_ids: set[str] = set()
    async with async_session_factory() as session:
        products = list(await session.scalars(select(Product)))
        for product in products:
            blob = f"{product.title} {product.subtitle} {product.category}"
            if not any(hint in blob for hint in LIGHT_HINTS):
                await session.delete(product)
                deleted += 1
                continue
            name, code = lighting_category(product.title)
            product.category = name
            product.category_code = code
            if "星途" not in (product.subtitle or ""):
                product.subtitle = f"星途户外照明 · {(product.subtitle or '').strip()}"
            keep_ids.add(product.product_id)
            updated += 1
        inv_rows = list(await session.scalars(select(ProductInventory)))
        for row in inv_rows:
            if row.product_id not in keep_ids:
                await session.delete(row)
        order_map = {
            "1001": "太阳能柱头灯",
            "1002": "中式户外壁灯",
            "1003": "LED 户外壁灯",
            "1004": "太阳能庭院灯",
            "1005": "新中式太阳能柱头灯",
        }
        for order in await session.scalars(select(Order)):
            if order.order_id in order_map:
                order.product = order_map[order.order_id]
        await session.commit()
    await reload_memory()
    print(f"Deleted {deleted} non-lighting products, recategorized {updated} lights.")


if __name__ == "__main__":
    asyncio.run(main())
