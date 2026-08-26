# 商品橱窗 API：面向前端展示的友好接口，数据来自模拟抖店商品数据
from decimal import Decimal
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from ..core.doudian_sim import find_product, list_categories, product_detail, search_products
from ..core.order_ids import build_order_id, now_china
from ..core.product_media import is_proxied_image_url
from ..db import async_session_factory
from ..models import Order, OrderItem, ProductInventory, User
from ..schemas import (
    CheckoutItemOut,
    CheckoutRequest,
    CheckoutResponse,
)
from .deps import get_current_user


router = APIRouter(prefix="/shop", tags=["shop"])


@router.get("/cover-proxy")
async def cover_proxy(u: str = Query(..., min_length=8, max_length=2000)):
    # 小程序无法稳定加载淘宝 CDN（防盗链、URL 含 !!），由后端带 Referer 转发
    if not is_proxied_image_url(u):
        raise HTTPException(status_code=400, detail="不支持的图片地址")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://item.taobao.com/",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }
    try:
        async with httpx.AsyncClient(follow_redirects=False, timeout=12.0) as client:
            upstream = await client.get(u, headers=headers)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="商品图片加载失败") from exc
    if upstream.status_code in (301, 302, 303, 307, 308):
        location = upstream.headers.get("location") or ""
        if not is_proxied_image_url(location):
            raise HTTPException(status_code=502, detail="商品图片加载失败")
        try:
            async with httpx.AsyncClient(follow_redirects=False, timeout=12.0) as client:
                upstream = await client.get(location, headers=headers)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="商品图片加载失败") from exc
    if upstream.status_code >= 400 or not upstream.content:
        raise HTTPException(status_code=502, detail="商品图片加载失败")
    content_type = (upstream.headers.get("content-type") or "image/jpeg").split(";")[0].strip()
    if not content_type.startswith("image/"):
        parsed = urlparse(u)
        if parsed.path.lower().endswith(".png"):
            content_type = "image/png"
        elif parsed.path.lower().endswith(".webp"):
            content_type = "image/webp"
        else:
            content_type = "image/jpeg"
    return StreamingResponse(iter([upstream.content]), media_type=content_type)


@router.get("/categories")
async def categories() -> list[dict]:
    # 商品分类与在售数量，供橱窗筛选栏展示（浏览不需要登录）
    return list_categories()


@router.get("/products")
async def products(
    q: str | None = None,
    category: str | None = None,
    page: int = 1,
    size: int = 20,
) -> dict:
    # 商品搜索：支持关键词、分类与分页，列表项不含详情大字段
    return search_products(keyword=q or "", category=category or "", page=page, size=size)


@router.get("/products/{product_id}")
async def product(
    product_id: str,
) -> dict:
    # 商品详情：返回图集、规格参数、SKU 与售后服务
    item = find_product(product_id)
    if item is None:
        raise HTTPException(status_code=404, detail="商品不存在")
    return product_detail(item)


@router.post("/checkout", response_model=CheckoutResponse)
async def checkout(
    payload: CheckoutRequest,
    user: User = Depends(get_current_user),
) -> CheckoutResponse:
    # 模拟真实下单流程：校验库存 → 扣减库存 → 创建订单与订单明细，全部在同一事务中完成
    if not payload.items:
        raise HTTPException(status_code=400, detail="购物车不能为空")

    # 1. 根据前端传入的 product_id 从内存商品数据查找商品信息与 SKU
    checkout_lines: list[dict] = []
    for req_item in payload.items:
        product = find_product(req_item.product_id)
        if product is None:
            raise HTTPException(status_code=404, detail=f"商品 {req_item.product_id} 不存在")
        if product.get("status") != "on_sale":
            raise HTTPException(status_code=400, detail=f"商品 {product['title']} 已下架")
        if req_item.quantity <= 0:
            raise HTTPException(status_code=400, detail="商品数量必须大于 0")
        skus = product.get("skus") or []
        if not skus:
            raise HTTPException(status_code=400, detail=f"商品 {product['title']} 暂无规格，无法下单")
        sku = skus[0]
        checkout_lines.append({
            "product_id": req_item.product_id,
            "sku_id": sku["sku_id"],
            "title": product["title"],
            "price": sku["price"],
            "quantity": req_item.quantity,
        })

    # 2. 在同一事务中完成库存校验、扣减与订单创建
    async with async_session_factory() as session:
        # 2a. 批量查询库存行并加锁（SQLite 无 SELECT FOR UPDATE，用普通查询）
        sku_ids = [line["sku_id"] for line in checkout_lines]
        inv_rows = (
            await session.scalars(
                select(ProductInventory).where(ProductInventory.sku_id.in_(sku_ids))
            )
        ).all()
        inv_map: dict[str, ProductInventory] = {row.sku_id: row for row in inv_rows}

        # 2b. 校验每个 SKU 的库存是否充足
        for line in checkout_lines:
            inv = inv_map.get(line["sku_id"])
            if inv is None:
                raise HTTPException(status_code=400, detail=f"SKU {line['sku_id']} 库存记录不存在")
            if inv.stock < line["quantity"]:
                raise HTTPException(
                    status_code=409,
                    detail=f"商品 {line['title']} 库存不足（剩余 {inv.stock}，需要 {line['quantity']}）",
                )

        product_names = "、".join(line["title"] for line in checkout_lines)
        total_amount = sum(Decimal(str(line["price"])) * line["quantity"] for line in checkout_lines)

        db_user = await session.get(User, user.id)
        if db_user is None:
            raise HTTPException(status_code=401, detail="用户不存在")
        wallet = Decimal(str(db_user.wallet_balance or 0))
        if wallet < total_amount:
            raise HTTPException(status_code=400, detail="钱包余额不足")

        # 2c. 扣减库存与钱包（虚拟下单，不发货）
        for line in checkout_lines:
            inv = inv_map[line["sku_id"]]
            inv.stock -= line["quantity"]
        db_user.wallet_balance = wallet - total_amount

        # 2d. 订单号为当前时间，例如 2024.12.3.8.23.12；同一秒冲突则追加序号
        stamp = now_china()
        order_id = build_order_id(stamp)
        seq = 1
        while await session.scalar(select(Order).where(Order.order_id == order_id)):
            order_id = build_order_id(stamp, seq)
            seq += 1

        # 2e. 创建订单主记录
        order = Order(
            order_id=order_id,
            user_id=db_user.id,
            customer=db_user.username,
            product=product_names,
            amount=total_amount,
            status="paid",
        )
        session.add(order)
        await session.flush()  # 获取 order.id

        # 2f. 创建订单明细项
        for line in checkout_lines:
            session.add(
                OrderItem(
                    order_db_id=order.id,
                    product_id=line["product_id"],
                    sku_id=line["sku_id"],
                    title=line["title"],
                    price=line["price"],
                    quantity=line["quantity"],
                )
            )

        await session.commit()
        remaining_balance = float(db_user.wallet_balance)

    # 3. 组装响应
    return CheckoutResponse(
        order_id=order_id,
        status="paid",
        total_amount=float(total_amount),
        remaining_balance=remaining_balance,
        items=[
            CheckoutItemOut(
                product_id=line["product_id"],
                sku_id=line["sku_id"],
                title=line["title"],
                price=line["price"],
                quantity=line["quantity"],
            )
            for line in checkout_lines
        ],
        created_at=order.created_at,
    )
