# 模拟抖店开放平台网关：以与真实 gateway 相同的请求/响应结构提供假数据
from typing import Any

from ..data.showcase import AFTER_SALES, PRODUCT_CATEGORIES, PRODUCTS
from .doudian_provider import DoudianProviderError, OrderNotFoundError, get_provider
from .product_media import proxied_media


def doudian_success(data: Any) -> dict[str, Any]:
    # 成功响应统一使用抖店网关的 err_no / err_msg / data 结构
    return {"err_no": 0, "err_msg": "success", "data": data}


def doudian_error(err_no: int, err_msg: str) -> dict[str, Any]:
    # 错误同样返回 HTTP 200，业务错误码放在响应体中，与真实网关一致
    return {"err_no": err_no, "err_msg": err_msg, "data": None}


def product_summary(product: dict) -> dict[str, Any]:
    # 商品列表项：价格转为 float，保证响应可 JSON 序列化
    return {
        "product_id": product.get("product_id", ""),
        "name": product.get("title", ""),
        "title": product.get("title", ""),
        "subtitle": product.get("subtitle") or "",
        "category": product.get("category") or "",
        "category_code": product.get("category_code") or "",
        "price": float(product.get("price") or 0),
        "market_price": float(product.get("original_price") or product.get("price") or 0),
        "original_price": float(product.get("original_price") or product.get("price") or 0),
        "sales_count": int(product.get("sales_count") or 0),
        "cover": proxied_media(product.get("cover") or ""),
        "cover_color": product.get("cover_color") or "#E5E7EB",
        "status": product.get("status") or "",
        "tags": list(product.get("tags") or []),
        "source_url": product.get("source_url", ""),
    }


def product_detail(product: dict) -> dict[str, Any]:
    # 商品详情：在列表字段基础上补充图集、规格、SKU 与售后服务
    data = product_summary(product)
    gallery = product.get("gallery") or []
    skus = product.get("skus") or []
    data.update(
        {
            "gallery": [proxied_media(item) for item in gallery if isinstance(item, str)],
            "description": product.get("description") or "",
            "specs": product.get("specs") or [],
            "services": product.get("services") or [],
            "sku_list": [
                {
                    "sku_id": sku.get("sku_id", ""),
                    "spec": sku.get("spec", ""),
                    "price": float(sku.get("price") or 0),
                    "stock": int(sku.get("stock") or 0),
                }
                for sku in skus
            ],
            # 橱窗详情页读取 skus，与 sku_list 保持同一份数据
            "skus": [
                {
                    "sku_id": sku.get("sku_id", ""),
                    "spec": sku.get("spec", ""),
                    "price": float(sku.get("price") or 0),
                    "stock": int(sku.get("stock") or 0),
                }
                for sku in skus
            ],
        }
    )
    return data


def filter_products(keyword: str = "", category: str = "") -> list[dict]:
    # 在售商品筛选：支持关键词与分类，并按销量倒序返回
    items = [p for p in PRODUCTS if p.get("status") == "on_sale"]
    if category:
        items = [
            p
            for p in items
            if p.get("category_code") == category or p.get("category") == category
        ]
    if keyword:
        lowered = keyword.lower()
        items = [
            p
            for p in items
            if lowered in (p.get("title") or "").lower()
            or lowered in (p.get("subtitle") or "").lower()
            or lowered in (p.get("description") or "").lower()
        ]
    return sorted(items, key=lambda p: p["sales_count"], reverse=True)


def search_products(keyword: str = "", category: str = "", page: int = 1, size: int = 20) -> dict:
    # 商品搜索统一分页逻辑，供友好接口与模拟网关复用
    page = max(1, page)
    size = min(50, max(1, size))
    items = filter_products(keyword, category)
    total = len(items)
    start = (page - 1) * size
    return {
        "items": [product_summary(p) for p in items[start : start + size]],
        "total": total,
        "page": page,
        "size": size,
    }


def find_product(product_id: str) -> dict | None:
    # 按商品 ID 查找橱窗商品，不存在时返回 None
    return next((p for p in PRODUCTS if p["product_id"] == product_id), None)


def list_categories() -> list[dict]:
    # 分类列表附带在售商品数量，方便前端展示计数角标
    categories = []
    for category in PRODUCT_CATEGORIES:
        count = sum(
            1
            for p in PRODUCTS
            if p.get("category_code") == category["code"] and p.get("status") == "on_sale"
        )
        categories.append({**category, "count": count})
    return [item for item in categories if item["count"] > 0]


def _parse_page(params: dict) -> tuple[int, int] | None:
    # 解析分页参数，格式错误时返回 None 交由上层返回业务错误
    try:
        page = int(params.get("page") or 1)
        size = int(params.get("size") or 20)
    except (TypeError, ValueError):
        return None
    return max(1, page), min(50, max(1, size))


def _after_sale_summary(item: dict) -> dict:
    # 售后单对外字段，金额转 float
    return {**item, "amount": float(item["amount"])}


async def _product_search(params: dict) -> dict[str, Any]:
    parsed = _parse_page(params)
    if parsed is None:
        return doudian_error(40002, "分页参数格式错误")
    page, size = parsed
    data = search_products(
        keyword=str(params.get("keyword") or ""),
        category=str(params.get("category") or ""),
        page=page,
        size=size,
    )
    return doudian_success(
        {
            "product_list": data["items"],
            "total": data["total"],
            "page": data["page"],
            "size": data["size"],
        }
    )


def _product_detail_by_id(params: dict) -> dict[str, Any]:
    product = find_product(str(params.get("product_id") or ""))
    if product is None:
        return doudian_error(40003, "商品不存在")
    return doudian_success({"product": product_detail(product)})


def _category_list() -> dict[str, Any]:
    categories = list_categories()
    return doudian_success({"category_list": categories, "total": len(categories)})


async def _order_detail(params: dict) -> dict[str, Any]:
    try:
        order = await get_provider().get_order(str(params.get("order_id") or ""))
    except OrderNotFoundError:
        return doudian_error(40004, "订单不存在")
    except DoudianProviderError as exc:
        return doudian_error(50000, str(exc))
    return doudian_success({"order": order})


async def _order_search_list(params: dict) -> dict[str, Any]:
    parsed = _parse_page(params)
    if parsed is None:
        return doudian_error(40002, "分页参数格式错误")
    page, size = parsed
    try:
        orders = await get_provider().list_orders(str(params.get("customer") or "") or None)
    except DoudianProviderError as exc:
        return doudian_error(50000, str(exc))
    start = (page - 1) * size
    return doudian_success(
        {
            "order_list": orders[start : start + size],
            "total": len(orders),
            "page": page,
            "size": size,
        }
    )


async def _sku_stock(params: dict) -> dict[str, Any]:
    sku_id = str(params.get("sku_id") or "")
    try:
        stock = await get_provider().get_inventory(sku_id)
    except DoudianProviderError as exc:
        return doudian_error(50001, str(exc))
    return doudian_success({"sku": {"sku_id": sku_id, "stock_num": stock}})


def _after_sale_list(params: dict) -> dict[str, Any]:
    parsed = _parse_page(params)
    if parsed is None:
        return doudian_error(40002, "分页参数格式错误")
    page, size = parsed
    status = str(params.get("status") or "").strip()
    items = [item for item in AFTER_SALES if not status or item["status"] == status]
    start = (page - 1) * size
    return doudian_success(
        {
            "after_sale_list": [_after_sale_summary(item) for item in items[start : start + size]],
            "total": len(items),
            "page": page,
            "size": size,
        }
    )


# 模拟网关支持的方法清单，供 /methods 接口展示
METHODS = [
    {
        "method": "product.categoryList",
        "description": "查询商品分类与在售数量",
        "params": {},
    },
    {
        "method": "product.search",
        "description": "按关键词与分类搜索在售商品",
        "params": {"keyword": "", "category": "post", "page": 1, "size": 20},
    },
    {
        "method": "product.detail",
        "description": "查询商品详情与 SKU",
        "params": {"product_id": "P10009"},
    },
    {
        "method": "order.searchList",
        "description": "按客户查询订单列表",
        "params": {"customer": "张三", "page": 1, "size": 20},
    },
    {
        "method": "order.orderDetail",
        "description": "查询订单详情",
        "params": {"order_id": "1001"},
    },
    {
        "method": "sku.stock",
        "description": "查询 SKU 实时库存",
        "params": {"sku_id": "SKU001"},
    },
    {
        "method": "afterSale.list",
        "description": "查询售后单列表",
        "params": {"status": "refunding", "page": 1, "size": 20},
    },
]


async def handle_doudian_method(method: str, params: dict) -> dict[str, Any]:
    # 统一网关分发入口：未知 method 返回与真实网关一致的业务错误
    if method == "product.categoryList":
        return _category_list()
    if method == "product.search":
        return await _product_search(params)
    if method == "product.detail":
        return _product_detail_by_id(params)
    if method == "order.searchList":
        return await _order_search_list(params)
    if method == "order.orderDetail":
        return await _order_detail(params)
    if method == "sku.stock":
        return await _sku_stock(params)
    if method == "afterSale.list":
        return _after_sale_list(params)
    return doudian_error(40001, f"模拟网关暂不支持 method: {method}")
