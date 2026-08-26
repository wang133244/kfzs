def _customer(api_client):
    login = api_client.post(
        "/api/v1/auth/login",
        json={"username": "customer", "password": "Customer@123"},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}, login.json()


def test_login_returns_user_id(api_client):
    _, body = _customer(api_client)
    assert body["user_id"] > 0


def test_cart_is_isolated_per_user(api_client):
    customer_headers, _ = _customer(api_client)
    wechat = api_client.post("/api/v1/auth/wechat", json={"local_key": "cart-user-b"}).json()
    other_headers = {"Authorization": f"Bearer {wechat['access_token']}"}

    empty = api_client.get("/api/v1/auth/me/cart", headers=customer_headers).json()
    assert empty["items"] == []

    saved = api_client.put(
        "/api/v1/auth/me/cart",
        headers=customer_headers,
        json={"items": [{"product": {"product_id": "P10001", "title": "灯"}, "quantity": 2}]},
    ).json()
    assert saved["items"][0]["quantity"] == 2

    other = api_client.get("/api/v1/auth/me/cart", headers=other_headers).json()
    assert other["items"] == []

    mine = api_client.get("/api/v1/auth/me/cart", headers=customer_headers).json()
    assert mine["items"][0]["product"]["product_id"] == "P10001"


def test_chat_reuses_same_session_until_deleted(api_client):
    headers, _ = _customer(api_client)
    first = api_client.post(
        "/api/v1/chat",
        headers=headers,
        json={"session_id": None, "message": "你好"},
    )
    assert first.status_code == 200
    session_id = first.json()["session_id"]

    second = api_client.post(
        "/api/v1/chat",
        headers=headers,
        json={"session_id": None, "message": "再问一句"},
    )
    assert second.status_code == 200
    assert second.json()["session_id"] == session_id

    history = api_client.get(f"/api/v1/sessions/{session_id}/messages", headers=headers).json()
    assert len(history) >= 4

    cleared = api_client.delete(f"/api/v1/sessions/{session_id}", headers=headers)
    assert cleared.status_code == 204

    third = api_client.post(
        "/api/v1/chat",
        headers=headers,
        json={"session_id": None, "message": "新的对话"},
    )
    assert third.status_code == 200
    assert third.json()["session_id"] != session_id
