# 商品橱窗与模拟抖店网关 API 测试
import json


def _login_headers(api_client) -> dict[str, str]:
    # 橱窗接口与主应用一样需要 JWT，统一复用登录凭证
    response = api_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "Admin@123456"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_shop_requires_auth(api_client):
    response = api_client.get("/api/v1/shop/products")
    assert response.status_code == 401


def test_shop_categories(api_client):
    body = api_client.get("/api/v1/shop/categories", headers=_login_headers(api_client)).json()
    assert len(body) >= 3
    assert all(category["count"] >= 1 for category in body)


def test_shop_products_search_and_category_filter(api_client):
    headers = _login_headers(api_client)
    body = api_client.get(
        "/api/v1/shop/products",
        headers=headers,
        params={"q": "柱头灯", "size": 2},
    ).json()
    assert body["total"] >= 1
    assert len(body["items"]) == min(2, body["total"])
    assert body["items"][0]["product_id"]

    digital = api_client.get(
        "/api/v1/shop/products",
        headers=headers,
        params={"category": "post", "size": 50},
    ).json()
    assert digital["total"] >= 1
    assert all(item["category_code"] == "post" for item in digital["items"])


def test_cover_proxy_rejects_ssrf_hosts(api_client):
    blocked = api_client.get(
        "/api/v1/shop/cover-proxy",
        params={"u": "http://127.0.0.1:8000/api/v1/auth/me"},
    )
    assert blocked.status_code == 400

    missing = api_client.get("/api/v1/shop/cover-proxy")
    assert missing.status_code == 422


def test_shop_product_covers_use_local_proxy_for_cdn():
    from app.core.product_media import proxied_media

    raw = "https://img.alicdn.com/imgextra/i3/demo/cover.jpg"
    proxied = proxied_media(raw)
    assert proxied.startswith("/api/v1/shop/cover-proxy?u=")
    assert "alicdn.com" in proxied
    assert proxied_media("/uploads/products/a.jpg") == "/uploads/products/a.jpg"
    assert proxied_media("https://evil.example/x.jpg") == "https://evil.example/x.jpg"


def test_shop_product_detail_and_404(api_client):
    headers = _login_headers(api_client)
    detail = api_client.get("/api/v1/shop/products/P10001", headers=headers).json()
    assert detail["title"]
    assert detail["sku_list"]
    assert detail["gallery"]
    assert detail["specs"]
    assert detail["cover"].startswith("/api/v1/shop/cover-proxy?u=")

    missing = api_client.get("/api/v1/shop/products/NOPE", headers=headers)
    assert missing.status_code == 404


def test_doudian_gateway_methods_and_search(api_client):
    headers = _login_headers(api_client)
    methods = api_client.get("/api/v1/sim/doudian/methods", headers=headers).json()
    assert any(item["method"] == "product.detail" for item in methods["methods"])

    response = api_client.post(
        "/api/v1/sim/doudian/router/rest",
        data={"method": "product.search", "param_json": json.dumps({"keyword": "柱头灯"})},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["err_no"] == 0
    assert body["data"]["product_list"]


def test_doudian_gateway_product_detail_and_order(api_client):
    headers = _login_headers(api_client)
    detail = api_client.post(
        "/api/v1/sim/doudian/router/rest",
        data={"method": "product.detail", "param_json": json.dumps({"product_id": "P10001"})},
        headers=headers,
    ).json()
    assert detail["err_no"] == 0
    assert detail["data"]["product"]["sku_list"]

    order = api_client.post(
        "/api/v1/sim/doudian/router/rest",
        data={"method": "order.orderDetail", "param_json": json.dumps({"order_id": "1001"})},
        headers=headers,
    ).json()
    assert order["err_no"] == 0
    assert order["data"]["order"]["order_id"] == "1001"


def test_doudian_gateway_error_codes(api_client):
    headers = _login_headers(api_client)
    unknown = api_client.post(
        "/api/v1/sim/doudian/router/rest",
        data={"method": "unknown.method", "param_json": "{}"},
        headers=headers,
    ).json()
    assert unknown["err_no"] == 40001

    bad_json = api_client.post(
        "/api/v1/sim/doudian/router/rest",
        data={"method": "product.search", "param_json": "{"},
        headers=headers,
    ).json()
    assert bad_json["err_no"] == 40002
