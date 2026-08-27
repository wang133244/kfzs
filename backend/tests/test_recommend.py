import random

from app.core.recommend import catalog_card_limit, has_explicit_need, parse_listed_indexes, recommend_products


def test_need_beats_purchase_history():
    result = recommend_products(
        "给我推荐一个壁灯",
        purchased_ids={"P10001"},
        purchased_categories=["post"],
        rng=random.Random(0),
    )
    assert result.strategy == "need"
    assert result.products
    assert all(
        item.get("category_code") == "wall" or "壁灯" in item.get("title", "")
        for item in result.products
    )


def test_history_when_user_has_no_need():
    result = recommend_products(
        "给我推荐一下",
        purchased_ids={"P10002"},
        purchased_categories=["wall"],
        rng=random.Random(0),
    )
    assert result.strategy == "history"
    assert result.products
    assert "P10002" not in {item["product_id"] for item in result.products}


def test_random_when_no_need_and_no_history():
    result = recommend_products("推荐一下", rng=random.Random(1))
    assert result.strategy == "random"
    assert result.products
    again = recommend_products("推荐一下", rng=random.Random(1))
    assert [item["product_id"] for item in again.products] == [
        item["product_id"] for item in result.products
    ]


def test_vague_recommend_is_not_explicit_need():
    assert has_explicit_need("给我推荐一下") is False
    assert has_explicit_need("推荐壁灯") is True
    assert has_explicit_need("柱头灯多少钱") is True


def test_compare_followup_is_not_a_four_card_catalog():
    assert catalog_card_limit("第一款和第三款有什么区别") == 2
    assert parse_listed_indexes("第一款和第三款有什么区别") == [1, 3]
    assert parse_listed_indexes("第二个怎么样") == [2]


def test_chat_recommends_from_purchase_history(api_client):
    login = api_client.post(
        "/api/v1/auth/wechat",
        json={"local_key": "rec-history-user", "username": "推荐用户"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    items = api_client.get("/api/v1/shop/products", headers=headers, params={"size": 50}).json()["items"]
    wall = next(item for item in items if item["category_code"] == "wall")
    checkout = api_client.post(
        "/api/v1/shop/checkout",
        headers=headers,
        json={"items": [{"product_id": wall["product_id"], "quantity": 1}]},
    )
    assert checkout.status_code == 200
    chat = api_client.post(
        "/api/v1/chat",
        headers=headers,
        json={"session_id": None, "message": "给我推荐一下"},
    )
    assert chat.status_code == 200
    body = chat.json()
    assert body["product_cards"]
    assert wall["product_id"] not in {card["product_id"] for card in body["product_cards"]}
