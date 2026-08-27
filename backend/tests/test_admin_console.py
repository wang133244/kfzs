def _login(api_client, username, password):
    response = api_client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body


def test_customer_and_admin_can_login(api_client):
    _, customer = _login(api_client, "customer", "Customer@123")
    assert customer["role"] == "customer"
    assert customer["username"] == "customer"
    _, admin = _login(api_client, "admin", "Admin@123456")
    assert admin["role"] == "admin"
    assert admin["username"] == "admin"


def test_admin_lists_customers_and_orders(api_client):
    customer_headers, _ = _login(api_client, "customer", "Customer@123")
    admin_headers, _ = _login(api_client, "admin", "Admin@123456")

    forbidden = api_client.get("/api/v1/admin/customers", headers=customer_headers)
    assert forbidden.status_code == 403

    customers = api_client.get("/api/v1/admin/customers", headers=admin_headers)
    assert customers.status_code == 200
    names = [item["username"] for item in customers.json()]
    assert "customer" in names
    row = next(item for item in customers.json() if item["username"] == "customer")
    assert "avatar_url" in row
    assert row["can_chat"] is False

    orders = api_client.get("/api/v1/admin/orders", headers=admin_headers)
    assert orders.status_code == 200
    assert orders.json()
    first = orders.json()[0]
    assert first["display_name"] == f"{first['customer']} {first['order_id']}"

    found = api_client.get("/api/v1/admin/orders?q=1001", headers=admin_headers)
    assert found.status_code == 200
    assert any(item["order_id"] == "1001" for item in found.json())


def test_admin_cannot_reply_before_handoff(api_client):
    customer_headers, _ = _login(api_client, "customer", "Customer@123")
    admin_headers, _ = _login(api_client, "admin", "Admin@123456")
    chat = api_client.post(
        "/api/v1/chat",
        headers=customer_headers,
        json={"session_id": None, "message": "柱头灯多少钱"},
    )
    assert chat.status_code == 200
    session_id = chat.json()["session_id"]
    denied = api_client.post(
        f"/api/v1/admin/human-chat/{session_id}/reply",
        headers=admin_headers,
        json={"content": "您好"},
    )
    assert denied.status_code == 400

    handed = api_client.post(
        "/api/v1/chat",
        headers=customer_headers,
        json={"session_id": session_id, "message": "转人工"},
    )
    assert handed.status_code == 200
    ok = api_client.post(
        f"/api/v1/admin/human-chat/{session_id}/reply",
        headers=admin_headers,
        json={"content": "人工已接入"},
    )
    assert ok.status_code == 200
    assert ok.json()["content"] == "人工已接入"
