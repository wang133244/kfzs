def _customer_token(api_client) -> str:
    login = api_client.post(
        "/api/v1/auth/login",
        json={"username": "customer", "password": "Customer@123"},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


def test_chat_ws_rejects_bad_token(api_client):
    with api_client.websocket_connect("/api/v1/chat/ws?token=bad") as ws:
        data = ws.receive_json()
        assert data["type"] == "error"
        assert "认证" in data["message"]


def test_chat_ws_returns_final_for_greeting(api_client):
    token = _customer_token(api_client)
    with api_client.websocket_connect(f"/api/v1/chat/ws?token={token}") as ws:
        ws.send_json({"message": "你好", "session_id": None})
        types = []
        final = None
        for _ in range(20):
            data = ws.receive_json()
            types.append(data["type"])
            if data["type"] == "final":
                final = data
                break
            if data["type"] == "error":
                raise AssertionError(data)
        assert final is not None
        assert "started" in types or "thinking" in types or "final" in types
        assert final["session_id"]
        assert final["message_id"] > 0
        assert final["response"]
        assert "product_cards" in final
