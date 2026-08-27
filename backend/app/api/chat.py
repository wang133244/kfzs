# 聊天会话相关 API 路由（REST 对话与 WebSocket 实时对话）
import json

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..agent.graph import run_agent, steps_from_state
from ..agent.llm import generate_chat_response_stream
from ..agent.nodes import should_skip_polish
from ..config import settings
from ..core.intent_router import is_explicit_handoff, is_handoff_affirmative
from ..core.memory import memory_service
from ..core.grounding import check_grounding
from ..core.safety import humanize_customer_text, validate_customer_answer
from ..core.ws_manager import ws_manager
from ..db import async_session_factory, get_db
from ..models import ChatSession, Message, User
from ..schemas import ChatRequest, ChatResponse
from ..security import decode_access_token
from .deps import get_current_user


router = APIRouter(tags=["chat"])


async def get_or_create_session(
    db: AsyncSession,
    user_id: int,
    session_id: str | None,
) -> ChatSession:
    if session_id:
        session = await db.get(ChatSession, session_id)
        if session is None or session.user_id != user_id:
            raise HTTPException(status_code=404, detail="会话不存在")
        return session
    # 未指定会话时复用该用户最近一次对话，保证下次打开仍是同一段记录
    latest = (
        await db.scalars(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.created_at.desc())
        )
    ).first()
    if latest is not None:
        return latest
    session = ChatSession(user_id=user_id, title="新会话")
    db.add(session)
    await db.flush()
    return session


HANDOFF_HOLD_REPLY = "已为您转接人工客服，消息已发送，请耐心等待客服回复。"


def _maybe_title_session(session: ChatSession, message: str) -> None:
    if session.title == "新会话":
        session.title = message[:20]


def _resume_ai_if_unconfirmed(session: ChatSession, message: str) -> bool:
    """未明确同意转人工时，按最新问题走智能客服，不锁死会话。"""
    if session.handoff_status not in ("waiting", "active"):
        return False
    if is_handoff_affirmative(message):
        return True
    session.handoff_status = "none"
    session.handled_by = None
    return False


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    session = await get_or_create_session(db, user.id, payload.session_id)
    _maybe_title_session(session, payload.message)
    db.add(
        Message(
            session_id=session.id,
            role="user",
            content=payload.message,
        )
    )
    await db.commit()
    if _resume_ai_if_unconfirmed(session, payload.message):
        return ChatResponse(
            session_id=session.id,
            message_id=0,
            response=HANDOFF_HOLD_REPLY,
            needs_human=True,
            route={"intent": "human_handoff", "action": "human_handoff", "slots": {}, "reason_code": "handoff_active"},
        )
    if session.handoff_status == "none":
        await db.commit()

    state = await run_agent(
        [{"role": "user", "content": payload.message}],
        str(user.id),
        session.id,
    )
    assistant = Message(
        session_id=session.id,
        role="assistant",
        content=state.get("final_response") or "",
        citations_json=json.dumps(state.get("citations") or [], ensure_ascii=False),
        product_cards_json=json.dumps(state.get("product_cards") or [], ensure_ascii=False),
    )
    db.add(assistant)
    await db.commit()
    if is_explicit_handoff(state):
        session.handoff_status = "waiting"
        await db.commit()
    await memory_service.refresh_summary(session.id, str(user.id))
    await db.refresh(assistant)
    await db.refresh(session)

    return ChatResponse(
        session_id=session.id,
        message_id=assistant.id,
        response=state.get("final_response") or "",
        citations=state.get("citations") or [],
        needs_human=bool(state.get("needs_human")),
        human_task_id=state.get("human_task_id"),
        steps=steps_from_state(state),
        citations_detail=state.get("citations_detail") or [],
        route={
            "intent": state.get("intent") or "unknown",
            "action": state.get("action") or "",
            "slots": state.get("slots") or {},
            "missing_slots": state.get("missing_slots") or [],
            "reason_code": state.get("reason_code") or "",
        },
        safety_blocked=bool(state.get("safety_blocked")),
        relevance_score=float(state.get("relevance_score") or 0.0),
        product_cards=state.get("product_cards") or [],
    )


@router.websocket("/chat/ws")
async def chat_ws(websocket: WebSocket, token: str = Query(...)) -> None:
    await websocket.accept()
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except Exception:
        await websocket.send_json({"type": "error", "message": "认证失败"})
        await websocket.close(code=4401)
        return

    async with async_session_factory() as db:
        user = await db.scalar(select(User).where(User.id == user_id))
        if user is None:
            await websocket.send_json({"type": "error", "message": "用户不存在"})
            await websocket.close(code=4401)
            return

        ws_manager.register(str(user_id), websocket)
        try:
            while True:
                data = await websocket.receive_json()
                message = str(data.get("message") or "").strip()
                if not message:
                    continue

                await websocket.send_json({"type": "status", "status": "started"})

                session = await get_or_create_session(db, user.id, data.get("session_id"))
                _maybe_title_session(session, message)
                db.add(
                    Message(
                        session_id=session.id,
                        role="user",
                        content=message,
                    )
                )
                await db.commit()
                if _resume_ai_if_unconfirmed(session, message):
                    await websocket.send_json(
                        {
                            "type": "final",
                            "session_id": session.id,
                            "message_id": 0,
                            "response": HANDOFF_HOLD_REPLY,
                            "citations": [],
                            "citations_detail": [],
                            "needs_human": True,
                            "human_task_id": None,
                            "route": {"intent": "human_handoff", "action": "human_handoff", "slots": {}, "reason_code": "handoff_active"},
                            "safety_blocked": False,
                        }
                    )
                    continue
                if session.handoff_status == "none":
                    await db.commit()

                state = await run_agent(
                    [{"role": "user", "content": message}],
                    str(user.id),
                    session.id,
                    stream_final=True,
                )

                await websocket.send_json(
                    {
                        "type": "thinking",
                        "step": "intent",
                        "label": state.get("intent") or "unknown",
                        "reason_code": state.get("reason_code") or "",
                        "slots": state.get("slots") or {},
                    }
                )
                for result in state.get("tool_results") or []:
                    await websocket.send_json(
                        {
                            "type": "tool",
                            "name": result.get("name"),
                            "arguments": result.get("arguments") or {},
                            "result": result.get("data") or {"error": result.get("error")},
                        }
                    )

                # 流式推送最终回复：逐 token 发 final_delta，首字延迟≈LLM 首 token
                final_response = state.get("final_response") or ""
                needs_human = bool(state.get("needs_human"))
                if not needs_human and settings.llm_provider.lower() != "mock" and not should_skip_polish(state):
                    collected = ""
                    async for piece in generate_chat_response_stream(state):
                        collected += piece
                        await websocket.send_json(
                            {
                                "type": "final_delta",
                                "session_id": session.id,
                                "delta": piece,
                            }
                        )
                    # 流式生成结果过 grounding + 安全校验，失败回退草稿
                    if collected:
                        grounded = check_grounding({**state, "final_response": collected})
                        if grounded["ok"]:
                            safety = validate_customer_answer("", collected)
                            if safety:
                                final_response = safety
                                needs_human = True
                                state["safety_blocked"] = True
                            else:
                                final_response = collected
                                state["final_response"] = collected

                final_response = humanize_customer_text(
                    final_response, state.get("product_cards") or []
                )
                assistant = Message(
                    session_id=session.id,
                    role="assistant",
                    content=final_response,
                    citations_json=json.dumps(state.get("citations") or [], ensure_ascii=False),
                    product_cards_json=json.dumps(state.get("product_cards") or [], ensure_ascii=False),
                )
                db.add(assistant)
                await db.commit()
                await db.refresh(assistant)
                if is_explicit_handoff(state):
                    session.handoff_status = "waiting"
                    await db.commit()
                await memory_service.refresh_summary(session.id, str(user.id))

                await websocket.send_json(
                    {
                        "type": "final",
                        "session_id": session.id,
                        "message_id": assistant.id,
                        "response": final_response,
                        "citations": state.get("citations") or [],
                        "citations_detail": state.get("citations_detail") or [],
                        "needs_human": needs_human,
                        "human_task_id": state.get("human_task_id"),
                        "route": {
                            "intent": state.get("intent") or "unknown",
                            "action": state.get("action") or "",
                            "slots": state.get("slots") or {},
                            "reason_code": state.get("reason_code") or "",
                        },
                        "safety_blocked": bool(state.get("safety_blocked")),
                        "relevance_score": float(state.get("relevance_score") or 0.0),
                        "product_cards": state.get("product_cards") or [],
                    }
                )
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            try:
                await websocket.send_json({"type": "error", "message": str(exc)})
            except Exception:
                pass
            await websocket.close()
        finally:
            ws_manager.unregister(str(user_id), websocket)
