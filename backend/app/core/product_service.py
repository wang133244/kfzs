# 商品服务：DB 持久化 + 内存同步。员工新增/下架商品时写入 DB 并实时更新
# showcase.PRODUCTS 内存列表（doudian_sim 直接读取该列表），无需改橱窗逻辑。
import json
from decimal import Decimal

from sqlalchemy import select

from ..data import showcase
from ..db import async_session_factory
from ..models import Product, ProductInventory


def _loads_list(raw: str | None) -> list:
    try:
        data = json.loads(raw or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def _product_to_dict(p: Product) -> dict:
    # 将 DB Product 行转换为 showcase.PRODUCTS 所需的字典结构
    return {
        "product_id": p.product_id,
        "title": p.title or "",
        "subtitle": p.subtitle or "",
        "category": p.category or "",
        "category_code": p.category_code or "",
        "price": p.price if isinstance(p.price, Decimal) else Decimal(str(p.price or 0)),
        "original_price": p.original_price if isinstance(p.original_price, Decimal) else Decimal(str(p.original_price or p.price or 0)),
        "sales_count": int(p.sales_count or 0),
        "cover": p.cover or "",
        "gallery": _loads_list(p.gallery_json),
        "cover_color": p.cover_color or "#E5E7EB",
        "description": p.description or "",
        "specs": _loads_list(p.specs_json),
        "skus": [
            {
                "sku_id": sku.get("sku_id", ""),
                "spec": sku.get("spec", ""),
                "price": Decimal(str(sku.get("price", "0"))),
                "stock": int(sku.get("stock", 0)),
                "threshold": int(sku.get("threshold", 5)),
            }
            for sku in _loads_list(p.skus_json)
            if isinstance(sku, dict)
        ],
        "status": p.status or "on_sale",
        "tags": [tag for tag in _loads_list(p.tags_json) if isinstance(tag, str)],
        "services": _loads_list(p.services_json),
        "source_url": p.source_url or "",
    }


def _sync_memory(products: list[Product]) -> None:
    # 用 DB 商品覆盖内存列表（原地变更，保持 doudian_sim 引用一致）
    showcase.PRODUCTS.clear()
    showcase.PRODUCTS.extend(_product_to_dict(p) for p in products)


async def _ensure_inventory(session, products: list[Product]) -> None:
    # 恢复/导入商品时可能只有商品行没有库存行，橱窗能看但下单会失败
    for product in products:
        for sku in _product_to_dict(product)["skus"]:
            sku_id = sku.get("sku_id") or ""
            if not sku_id:
                continue
            existing = await session.scalar(
                select(ProductInventory).where(ProductInventory.sku_id == sku_id)
            )
            if existing is None:
                session.add(
                    ProductInventory(
                        sku_id=sku_id,
                        product_id=product.product_id,
                        sku_name=product.title,
                        stock=int(sku.get("stock") or 50),
                        threshold=int(sku.get("threshold") or 5),
                    )
                )


async def seed_and_sync_products() -> None:
    # 启动时调用：DB 为空则从 showcase 种子导入，随后同步到内存
    async with async_session_factory() as session:
        count = await session.scalar(select(Product))
        if not count:
            for item in showcase.PRODUCTS:
                session.add(
                    Product(
                        product_id=item["product_id"],
                        title=item["title"],
                        subtitle=item.get("subtitle", ""),
                        category=item.get("category", "柱头灯"),
                        category_code=item.get("category_code", "post"),
                        price=item["price"],
                        original_price=item["original_price"],
                        sales_count=item.get("sales_count", 0),
                        cover=item.get("cover", ""),
                        cover_color=item.get("cover_color", "#E5E7EB"),
                        description=item.get("description", ""),
                        gallery_json=json.dumps(item.get("gallery", []), ensure_ascii=False),
                        specs_json=json.dumps(item.get("specs", []), ensure_ascii=False),
                        skus_json=json.dumps(
                            [{**sku, "price": float(sku["price"])} for sku in item.get("skus", [])],
                            ensure_ascii=False,
                        ),
                        services_json=json.dumps(item.get("services", []), ensure_ascii=False),
                        tags_json=json.dumps(item.get("tags", []), ensure_ascii=False),
                        status=item.get("status", "on_sale"),
                        source_url=item.get("source_url", ""),
                    )
                )
            await session.commit()
        result = await session.scalars(select(Product).order_by(Product.id))
        products = list(result)
        await _ensure_inventory(session, products)
        await session.commit()
        _sync_memory(products)
    from .product_knowledge import sync_from_memory

    sync_from_memory(rebuild_index=False)


async def reload_memory() -> None:
    # 从 DB 重新同步内存列表（删除/新增后调用）
    async with async_session_factory() as session:
        result = await session.scalars(select(Product).order_by(Product.id))
        _sync_memory(list(result))
    from .product_knowledge import sync_from_memory

    sync_from_memory(rebuild_index=True)


async def create_product(data: dict) -> dict:
    # 员工新增商品：写入 DB 后同步内存，返回商品字典
    async with async_session_factory() as session:
        existing = await session.scalar(select(Product).order_by(Product.id.desc()))
        next_num = 1
        if existing and existing.product_id.startswith("P"):
            try:
                next_num = int(existing.product_id[1:]) + 1
            except ValueError:
                next_num = len(showcase.PRODUCTS) + 10009
        product_id = f"P{next_num}"
        price = Decimal(str(data.get("price", 0)))
        original = Decimal(str(data.get("original_price") or data.get("price", 0)))
        product = Product(
            product_id=product_id,
            title=data["title"],
            subtitle=data.get("subtitle", ""),
            category=data.get("category", "柱头灯"),
            category_code=data.get("category_code", "post"),
            price=price,
            original_price=original,
            sales_count=int(data.get("sales_count", 0)),
            cover=data.get("cover", ""),
            cover_color=data.get("cover_color", "#E5E7EB"),
            description=data.get("description", ""),
            gallery_json=json.dumps(data.get("gallery", []), ensure_ascii=False),
            specs_json=json.dumps(data.get("specs", []), ensure_ascii=False),
            skus_json=json.dumps(data.get("skus", []), ensure_ascii=False),
            services_json=json.dumps(data.get("services", []), ensure_ascii=False),
            tags_json=json.dumps(data.get("tags", []), ensure_ascii=False),
            status=data.get("status", "on_sale"),
            source_url=data.get("source_url", ""),
        )
        session.add(product)
        await session.commit()
        await session.refresh(product)
    await reload_memory()
    return _product_to_dict(product)


async def delete_product(product_id: str) -> bool:
    # 员工下架/删除商品：从 DB 移除后同步内存
    async with async_session_factory() as session:
        product = await session.scalar(select(Product).where(Product.product_id == product_id))
        if product is None:
            return False
        await session.delete(product)
        await session.commit()
    await reload_memory()
    return True


async def update_product_fields(product_id: str, data: dict) -> dict | None:
    # 按字段更新商品（图集、详情、价格等），写入 DB 后同步内存
    async with async_session_factory() as session:
        product = await session.scalar(select(Product).where(Product.product_id == product_id))
        if product is None:
            return None
        mapping = {
            "title": "title",
            "subtitle": "subtitle",
            "description": "description",
            "cover": "cover",
            "cover_color": "cover_color",
            "source_url": "source_url",
            "status": "status",
            "category": "category",
            "category_code": "category_code",
        }
        for src, dest in mapping.items():
            if src in data and data[src] is not None:
                setattr(product, dest, data[src])
        if "price" in data and data["price"] is not None:
            product.price = Decimal(str(data["price"]))
        if "original_price" in data and data["original_price"] is not None:
            product.original_price = Decimal(str(data["original_price"]))
        if "sales_count" in data and data["sales_count"] is not None:
            product.sales_count = int(data["sales_count"])
        if "gallery" in data:
            product.gallery_json = json.dumps(data["gallery"] or [], ensure_ascii=False)
        if "specs" in data:
            product.specs_json = json.dumps(data["specs"] or [], ensure_ascii=False)
        if "skus" in data:
            product.skus_json = json.dumps(data["skus"] or [], ensure_ascii=False)
        if "services" in data:
            product.services_json = json.dumps(data["services"] or [], ensure_ascii=False)
        if "tags" in data:
            product.tags_json = json.dumps(data["tags"] or [], ensure_ascii=False)
        await session.commit()
        await session.refresh(product)
        result = _product_to_dict(product)
    await reload_memory()
    return result


async def update_product_status(product_id: str, status: str) -> dict | None:
    # 员工切换商品上下架状态
    async with async_session_factory() as session:
        product = await session.scalar(select(Product).where(Product.product_id == product_id))
        if product is None:
            return None
        product.status = status
        await session.commit()
        await session.refresh(product)
        result = _product_to_dict(product)
    await reload_memory()
    return result


async def list_products_for_manage() -> list[dict]:
    # 商品管理列表：返回 DB 全部商品（含已下架）
    async with async_session_factory() as session:
        result = await session.scalars(select(Product).order_by(Product.id.desc()))
        return [_product_to_dict(p) for p in result]
