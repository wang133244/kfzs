# WebSocket 连接管理器：按 user_id 维护活跃连接，供审核通过后向顾客推送正式回复。
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    """维护 user_id -> WebSocket 连接集合，支持向指定用户推送消息。"""

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}

    def register(self, user_id: str, websocket: WebSocket) -> None:
        self._connections.setdefault(user_id, set()).add(websocket)

    def unregister(self, user_id: str, websocket: WebSocket) -> None:
        conns = self._connections.get(user_id)
        if conns:
            conns.discard(websocket)
            if not conns:
                del self._connections[user_id]

    async def send_to_user(self, user_id: str, message: dict[str, Any]) -> bool:
        """向指定用户的所有活跃连接推送 JSON 消息，返回是否至少送达一条。"""
        conns = self._connections.get(user_id)
        if not conns:
            return False
        delivered = False
        for ws in list(conns):
            try:
                await ws.send_json(message)
                delivered = True
            except Exception:
                # 连接已断开，清理掉
                self.unregister(user_id, ws)
        return delivered


# 全局单例，供 chat.py 注册连接、admin.py 推送审核结果复用
ws_manager = ConnectionManager()
