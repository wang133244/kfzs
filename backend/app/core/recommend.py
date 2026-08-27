# 客服商品推荐：有明确需求按需求；否则按历史购买同类；再没有则随机
from __future__ import annotations

import random
import re
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import select

from .doudian_sim import filter_products, find_product
from .product_media import proxied_media
from ..db import async_session_factory
from ..models import Order, OrderItem

_QUESTION_STOP_WORDS = (
    "我想了解", "请问", "有没有", "你们有什么", "介绍一下", "了解一下",
    "给我推荐", "推荐一个", "推荐一款", "推荐一下", "给我", "推荐",
    "一个", "一款", "一下", "哪款", "哪一款", "想买", "看看",
    "怎么样", "多少钱", "价格", "商品", "产品", "能", "可以", "吗", "呢", "啊",
    "有什么", "哪些", "介绍", "随便",
)
_CATEGORY_HINTS = ("户外壁灯", "柱头灯", "庭院灯", "壁灯", "太阳能")
_CATEGORY_CODE_HINTS = (
    ("户外壁灯", "wall"),
    ("壁灯", "wall"),
    ("柱头灯", "post"),
    ("庭院灯", "solar"),
)
_GENERIC_KEYWORDS = {"", "灯", "灯具", "好灯", "好的"}
_PAID_STATUSES = ("paid", "shipped")


@dataclass(frozen=True)
class RecommendResult:
    products: list[dict]
    strategy: str  # need | history | random


def catalog_card_limit(message: str) -> int:
    text = message or ""
    if parse_listed_indexes(text) or any(word in text for word in ("区别", "对比", "哪个好", "哪款好")):
        return 2
    if any(word in text for word in ("有什么", "推荐", "哪些", "介绍")):
        return 4
    return 2


_CN_INDEX = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


def parse_listed_indexes(message: str) -> list[int]:
    # 「第一款 / 第3个」→ 1-based 序号，用于从上一轮推荐里挑卡片
    found: list[int] = []
    for match in re.finditer(r"第\s*([一二两三四五六七八九十\d]+)\s*[款个盏只项]", message or ""):
        token = match.group(1)
        index = int(token) if token.isdigit() else _CN_INDEX.get(token)
        if index and index not in found:
            found.append(index)
    return found


def cards_from_ids(product_ids: list[str]) -> list[dict]:
    cards = []
    for product_id in product_ids:
        product = find_product(product_id)
        if product:
            cards.append(product_to_card(product))
    return cards


def extract_search_keyword(message: str) -> str:
    for hint in _CATEGORY_HINTS:
        if hint in message:
            return hint
    text = message
    for word in _QUESTION_STOP_WORDS:
        text = text.replace(word, "")
    return text.strip()


def has_explicit_need(message: str) -> bool:
    if any(hint in message for hint in _CATEGORY_HINTS):
        return True
    keyword = extract_search_keyword(message)
    return bool(keyword) and keyword not in _GENERIC_KEYWORDS


def product_to_card(product: dict) -> dict:
    return {
        "product_id": product.get("product_id", ""),
        "title": product.get("title", ""),
        "subtitle": product.get("subtitle", ""),
        "category": product.get("category", ""),
        "price": float(product.get("price", 0)),
        "original_price": float(product.get("original_price") or product.get("price") or 0),
        "cover": proxied_media(product.get("cover", "")),
        "cover_color": product.get("cover_color", "#E5E7EB"),
        "sales_count": int(product.get("sales_count") or 0),
        "tags": list(product.get("tags") or []),
        "source_url": product.get("source_url", ""),
        "category_code": product.get("category_code", ""),
    }


def match_by_need(message: str) -> list[dict]:
    lowered = message.lower()
    matches: list[dict] = []
    for product in filter_products():
        title = (product.get("title") or "").lower()
        if title and title in lowered:
            matches.append(product)
    if not matches:
        keyword = extract_search_keyword(message)
        if keyword and keyword not in _GENERIC_KEYWORDS:
            matches = filter_products(keyword=keyword)
    if not matches:
        for hint, code in _CATEGORY_CODE_HINTS:
            if hint in message:
                matches = filter_products(category=code)
                break
    return matches


def match_by_history(purchased_ids: set[str], category_codes: list[str], limit: int) -> list[dict]:
    catalog = filter_products()
    bought = {pid for pid in purchased_ids if pid}
    ranked_cats = [code for code, _ in Counter(category_codes).most_common() if code]
    picked: list[dict] = []
    seen: set[str] = set()

    def take(predicate) -> None:
        for product in catalog:
            pid = product.get("product_id") or ""
            if not pid or pid in bought or pid in seen:
                continue
            if predicate(product):
                picked.append(product)
                seen.add(pid)
                if len(picked) >= limit:
                    return

    for cat in ranked_cats:
        take(lambda p, code=cat: p.get("category_code") == code or p.get("category") == code)
        if len(picked) >= limit:
            return picked
    take(lambda _p: True)
    return picked


def match_random(limit: int, rng: random.Random) -> list[dict]:
    catalog = list(filter_products())
    if not catalog:
        return []
    k = min(limit, len(catalog))
    return rng.sample(catalog, k)


def recommend_products(
    message: str,
    purchased_ids: set[str] | None = None,
    purchased_categories: list[str] | None = None,
    limit: int | None = None,
    rng: random.Random | None = None,
) -> RecommendResult:
    size = catalog_card_limit(message) if limit is None else max(1, limit)
    picker = rng or random.Random()
    bought = purchased_ids or set()
    categories = purchased_categories or []

    if has_explicit_need(message):
        need_hits = match_by_need(message)
        if need_hits:
            return RecommendResult(need_hits[:size], "need")

    if bought:
        history_hits = match_by_history(bought, categories, size)
        if history_hits:
            return RecommendResult(history_hits, "history")

    return RecommendResult(match_random(size, picker), "random")


async def load_purchase_profile(user_id: str) -> tuple[set[str], list[str]]:
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return set(), []
    async with async_session_factory() as session:
        rows = (
            await session.execute(
                select(OrderItem.product_id)
                .join(Order, OrderItem.order_db_id == Order.id)
                .where(Order.user_id == uid)
                .where(Order.status.in_(_PAID_STATUSES))
            )
        ).all()
    product_ids = [row[0] for row in rows if row[0]]
    categories: list[str] = []
    for product_id in product_ids:
        product = find_product(product_id)
        if product and product.get("category_code"):
            categories.append(str(product["category_code"]))
        elif product and product.get("category"):
            categories.append(str(product["category"]))
    return set(product_ids), categories


async def recommend_for_user(
    message: str,
    user_id: str,
    limit: int | None = None,
    rng: random.Random | None = None,
) -> RecommendResult:
    purchased_ids, purchased_categories = await load_purchase_profile(user_id)
    return recommend_products(
        message,
        purchased_ids=purchased_ids,
        purchased_categories=purchased_categories,
        limit=limit,
        rng=rng,
    )


def cards_from_result(result: RecommendResult) -> list[dict]:
    return [product_to_card(product) for product in result.products]
