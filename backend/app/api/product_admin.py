# 商品管理 API：员工新增/下架/删除商品，仅限 staff / admin 角色访问。
from fastapi import APIRouter, Depends, HTTPException

from ..core.product_service import (
    create_product,
    delete_product,
    list_products_for_manage,
    update_product_status,
)
from ..core.crawler import crawl_product_page
from ..models import User
from ..schemas import ProductCreate
from .deps import get_current_staff


router = APIRouter(prefix="/admin/products", tags=["product-admin"])


@router.get("")
async def list_products(user: User = Depends(get_current_staff)) -> list[dict]:
    # 商品管理列表：返回全部商品（含已下架），按创建时间倒序
    items = await list_products_for_manage()
    return [
        {
            "product_id": p["product_id"],
            "title": p["title"],
            "subtitle": p["subtitle"],
            "category": p["category"],
            "category_code": p["category_code"],
            "price": float(p["price"]),
            "original_price": float(p["original_price"]),
            "sales_count": p["sales_count"],
            "cover": p["cover"],
            "status": p["status"],
            "tags": p["tags"],
            "source_url": p.get("source_url", ""),
        }
        for p in items
    ]


@router.post("")
async def add_product(
    payload: ProductCreate,
    user: User = Depends(get_current_staff),
) -> dict:
    # 员工新增商品：写入 DB 并同步内存橱窗
    data = payload.model_dump()
    product = await create_product(data)
    return {
        "product_id": product["product_id"],
        "title": product["title"],
        "status": product["status"],
        "created": True,
    }


@router.delete("/{product_id}")
async def remove_product(
    product_id: str,
    user: User = Depends(get_current_staff),
) -> dict:
    # 员工删除/下架商品
    if not await delete_product(product_id):
        raise HTTPException(404, "商品不存在")
    return {"deleted": True, "product_id": product_id}


@router.post("/{product_id}/status")
async def change_status(
    product_id: str,
    payload: dict,
    user: User = Depends(get_current_staff),
) -> dict:
    # 切换商品上下架状态：on_sale / off_shelf
    status = str(payload.get("status") or "").strip()
    if status not in ("on_sale", "off_shelf"):
        raise HTTPException(400, "状态仅支持 on_sale 或 off_shelf")
    product = await update_product_status(product_id, status)
    if product is None:
        raise HTTPException(404, "商品不存在")
    return {"product_id": product["product_id"], "status": product["status"]}


@router.post("/crawl")
async def crawl_product(
    payload: dict,
    user: User = Depends(get_current_staff),
) -> dict:
    # 从商品链接爬取预填数据：OpenCLI 通过已登录 Chrome 抓取页面后提取标题/价格/主图等，供员工确认后保存
    url = str(payload.get("url") or "").strip()
    if not url or not url.startswith("http"):
        raise HTTPException(400, "请提供有效的商品链接（http/https 开头）")
    try:
        data = await crawl_product_page(url)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"crawled": True, "data": data}
