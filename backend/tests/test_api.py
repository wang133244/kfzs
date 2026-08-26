from app.core.tools import process_refund


def test_healthz(api_client):
    response = api_client.get("/api/v1/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_login_returns_token(api_client):
    response = api_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "Admin@123456"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_chat_requires_auth(api_client):
    response = api_client.post(
        "/api/v1/chat",
        json={"session_id": None, "message": "查一下订单 1001"},
    )
    assert response.status_code == 401


def test_chat_contract(api_client):
    login = api_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "Admin@123456"},
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    response = api_client.post(
        "/api/v1/chat",
        headers=headers,
        json={"session_id": None, "message": "查一下订单 1001"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["session_id"]
    assert body["message_id"] > 0
    assert "1001" in body["response"]
    assert isinstance(body["citations"], list)
    assert body["needs_human"] is False
    assert any(step["type"] == "intent" for step in body["steps"])


def test_chat_history_keeps_product_cards(api_client):
    login = api_client.post(
        "/api/v1/auth/login",
        json={"username": "customer", "password": "Customer@123"},
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    response = api_client.post(
        "/api/v1/chat",
        headers=headers,
        json={"session_id": None, "message": "给我推荐一个壁灯"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["product_cards"]
    assert body["product_cards"][0]["cover"]
    history = api_client.get(f"/api/v1/sessions/{body['session_id']}/messages", headers=headers)
    assert history.status_code == 200
    assistant = [item for item in history.json() if item["role"] == "assistant"][-1]
    assert assistant["product_cards"]
    assert assistant["product_cards"][0]["cover"]
    assert assistant["product_cards"][0]["product_id"]


def _customer_headers(api_client):
    login = api_client.post(
        "/api/v1/auth/login",
        json={"username": "customer", "password": "Customer@123"},
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _staff_headers(api_client):
    login = api_client.post(
        "/api/v1/auth/login",
        json={"username": "staff", "password": "Staff@123456"},
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_customer_can_clear_own_session(api_client):
    headers = _customer_headers(api_client)
    response = api_client.post(
        "/api/v1/chat",
        headers=headers,
        json={"session_id": None, "message": "查一下订单 1001"},
    )
    assert response.status_code == 200
    session_id = response.json()["session_id"]
    history = api_client.get(f"/api/v1/sessions/{session_id}/messages", headers=headers)
    assert len(history.json()) >= 2

    cleared = api_client.delete(f"/api/v1/sessions/{session_id}", headers=headers)
    assert cleared.status_code == 204

    missing = api_client.get(f"/api/v1/sessions/{session_id}/messages", headers=headers)
    assert missing.status_code == 404
    remaining = api_client.get("/api/v1/sessions", headers=headers)
    assert all(item["id"] != session_id for item in remaining.json())


def test_staff_can_read_customer_session_messages(api_client):
    customer = _customer_headers(api_client)
    response = api_client.post(
        "/api/v1/chat",
        headers=customer,
        json={"session_id": None, "message": "给我推荐一个壁灯"},
    )
    session_id = response.json()["session_id"]

    staff = _staff_headers(api_client)
    history = api_client.get(f"/api/v1/admin/sessions/{session_id}/messages", headers=staff)
    assert history.status_code == 200
    roles = [item["role"] for item in history.json()]
    assert "user" in roles
    assert "assistant" in roles
    assistant = [item for item in history.json() if item["role"] == "assistant"][-1]
    assert assistant["product_cards"]
    assert assistant["product_cards"][0]["cover"]


def test_customer_cannot_read_admin_session_messages(api_client):
    customer = _customer_headers(api_client)
    response = api_client.post(
        "/api/v1/chat",
        headers=customer,
        json={"session_id": None, "message": "你好"},
    )
    session_id = response.json()["session_id"]
    forbidden = api_client.get(
        f"/api/v1/admin/sessions/{session_id}/messages",
        headers=customer,
    )
    assert forbidden.status_code == 403


def test_admin_approves_refund_task(api_client):
    import asyncio

    from app.db import async_session_factory
    from app.models import HumanTask
    from sqlalchemy import select

    task_result = asyncio.run(process_refund("1002", "refund", "测试退款"))
    task_id = task_result["task_id"]

    login = api_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "Admin@123456"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = api_client.post(f"/api/v1/admin/tasks/{task_id}/approve", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "approved"

    async def check_task():
        async with async_session_factory() as session:
            task = await session.get(HumanTask, task_id)
            return task.status

    assert asyncio.run(check_task()) == "approved"


def test_unconfirmed_handoff_follows_latest_product_question(api_client):
    headers = _customer_headers(api_client)
    first = api_client.post(
        "/api/v1/chat",
        headers=headers,
        json={"session_id": None, "message": "今天天气怎么样"},
    )
    assert first.status_code == 200
    session_id = first.json()["session_id"]
    assert first.json()["needs_human"] is False
    assert "是否需要转人工" in first.json()["response"]

    second = api_client.post(
        "/api/v1/chat",
        headers=headers,
        json={
            "session_id": session_id,
            "message": "我想了解太阳能柱头灯户外防水现代简约LED庭院灯福字方形围墙灯后现代",
        },
    )
    assert second.status_code == 200
    body = second.json()
    assert "已为您转接人工客服" not in body["response"]
    assert body["needs_human"] is False
    assert body.get("product_cards")
    assert any(
        "柱头灯" in (card.get("title") or "") or "柱头灯" in (card.get("category") or "")
        for card in body["product_cards"]
    )


def test_waiting_session_resumes_on_new_question(api_client):
    headers = _customer_headers(api_client)
    handed = api_client.post(
        "/api/v1/chat",
        headers=headers,
        json={"session_id": None, "message": "转人工"},
    )
    assert handed.status_code == 200
    session_id = handed.json()["session_id"]
    assert handed.json()["needs_human"] is True

    follow = api_client.post(
        "/api/v1/chat",
        headers=headers,
        json={"session_id": session_id, "message": "给我推荐一个壁灯"},
    )
    assert follow.status_code == 200
    body = follow.json()
    assert "已为您转接人工客服" not in body["response"]
    assert body.get("product_cards")
