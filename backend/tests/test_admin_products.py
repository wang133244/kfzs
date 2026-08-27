def _login(api_client, username, password):
    response = api_client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _shop_ids(api_client, keyword=""):
    params = {"size": 50}
    if keyword:
        params["q"] = keyword
    body = api_client.get("/api/v1/shop/products", params=params).json()
    return {item["product_id"] for item in body["items"]}


def test_customer_cannot_manage_products(api_client):
    headers = _login(api_client, "customer", "Customer@123")
    created = api_client.post(
        "/api/v1/admin/products",
        headers=headers,
        json={"title": "顾客不应能添加", "price": 1},
    )
    assert created.status_code == 403


def test_admin_can_create_update_off_shelf_and_delete_product(api_client):
    headers = _login(api_client, "admin", "Admin@123456")
    created = api_client.post(
        "/api/v1/admin/products",
        headers=headers,
        json={
            "title": "管理员新增测试灯",
            "category": "太阳能庭院灯",
            "category_code": "solar",
            "price": 199,
            "description": "用于测试的灯具",
        },
    )
    assert created.status_code == 200, created.text
    product_id = created.json()["product_id"]
    assert product_id
    assert created.json()["status"] == "on_sale"

    detail = api_client.get(f"/api/v1/shop/products/{product_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["title"] == "管理员新增测试灯"
    assert body["price"] == 199
    assert body["skus"]
    assert body["skus"][0]["sku_id"]
    assert product_id in _shop_ids(api_client, "管理员新增测试灯")

    updated = api_client.patch(
        f"/api/v1/admin/products/{product_id}",
        headers=headers,
        json={"title": "管理员改价测试灯", "price": 88},
    )
    assert updated.status_code == 200, updated.text
    renamed = api_client.get(f"/api/v1/shop/products/{product_id}").json()
    assert renamed["title"] == "管理员改价测试灯"
    assert renamed["price"] == 88

    off = api_client.post(
        f"/api/v1/admin/products/{product_id}/status",
        headers=headers,
        json={"status": "off_shelf"},
    )
    assert off.status_code == 200
    assert off.json()["status"] == "off_shelf"
    assert product_id not in _shop_ids(api_client, "管理员改价测试灯")

    managed = api_client.get("/api/v1/admin/products", headers=headers)
    assert managed.status_code == 200
    row = next(item for item in managed.json() if item["product_id"] == product_id)
    assert row["status"] == "off_shelf"
    assert row["title"] == "管理员改价测试灯"

    on = api_client.post(
        f"/api/v1/admin/products/{product_id}/status",
        headers=headers,
        json={"status": "on_sale"},
    )
    assert on.status_code == 200
    assert product_id in _shop_ids(api_client, "管理员改价测试灯")

    deleted = api_client.delete(f"/api/v1/admin/products/{product_id}", headers=headers)
    assert deleted.status_code == 200
    missing = api_client.get(f"/api/v1/shop/products/{product_id}")
    assert missing.status_code == 404
