# 人工客服 API：员工查看转人工会话队列、查看顾客历史消息、直接回复顾客、关闭转人工。
# 全部接口仅限 staff / admin 角色访问。
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import ChatSession, Message, User
from ..schemas import HandoffSessionOut, MessageOut
from .deps import get_current_staff


router = APIRouter(prefix="/admin/human-chat", tags=["human-chat"])


@router.get("/sessions", response_model=list[HandoffSessionOut])
async def list_handoff_sessions(
    user: User = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    # 返回所有处于 waiting / active 的转人工会话，附带顾客名与最近消息
    stmt = (
        select(ChatSession)
        .where(ChatSession.handoff_status.in_(("waiting", "active")))
        .order_by(ChatSession.created_at.desc())
    )
    sessions = (await db.scalars(stmt)).all()
    result = []
    for s in sessions:
        customer = await db.scalar(select(User).where(User.id == s.user_id))
        last_msg = await db.scalar(
            select(Message)
            .where(Message.session_id == s.id)
            .order_by(Message.id.desc())
        )
        result.append(
            HandoffSessionOut(
                id=s.id,
                title=s.title,
                customer=customer.username if customer else "未知用户",
                handoff_status=s.handoff_status,
                created_at=s.created_at,
                last_message=last_msg.content[:60] if last_msg else "",
                last_role=last_msg.role if last_msg else "",
            )
        )
    return result


@router.get("/{session_id}/messages", response_model=list[MessageOut])
async def get_session_messages(
    session_id: str,
    user: User = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    # 员工可查看任意转人工会话的完整消息历史
    session = await db.get(ChatSession, session_id)
    if session is None:
        raise HTTPException(404, "会话不存在")
    stmt = select(Message).where(Message.session_id == session_id).order_by(Message.id.asc())
    return (await db.scalars(stmt)).all()


@router.post("/{session_id}/reply", response_model=MessageOut)
async def reply_to_session(
    session_id: str,
    payload: dict,
    user: User = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    # 员工发送回复：写入 role=staff 消息，会话状态置为 active
    session = await db.get(ChatSession, session_id)
    if session is None:
        raise HTTPException(404, "会话不存在")
    content = str(payload.get("content") or "").strip()
    if not content:
        raise HTTPException(400, "回复内容不能为空")
    session.handoff_status = "active"
    session.handled_by = user.id
    msg = Message(session_id=session_id, role="staff", content=content)
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg


@router.post("/{session_id}/close", response_model=HandoffSessionOut)
async def close_handoff(
    session_id: str,
    user: User = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    # 员工结束人工接入：会话状态置为 closed，顾客后续消息重新走 AI
    session = await db.get(ChatSession, session_id)
    if session is None:
        raise HTTPException(404, "会话不存在")
    session.handoff_status = "closed"
    await db.commit()
    await db.refresh(session)
    customer = await db.scalar(select(User).where(User.id == session.user_id))
    return HandoffSessionOut(
        id=session.id,
        title=session.title,
        customer=customer.username if customer else "未知用户",
        handoff_status=session.handoff_status,
        created_at=session.created_at,
        last_message="",
        last_role="",
    )
