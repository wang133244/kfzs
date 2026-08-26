# 会话历史相关 API 路由（会话列表、创建会话、消息记录查询与清空对话）
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import ChatSession, ConversationSummary, Message, User, WorkflowState
from ..schemas import MessageOut, SessionCreate, SessionOut
from .deps import get_current_user


router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionOut])
async def list_sessions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 当前用户的会话列表，按创建时间倒序
    stmt = (
        select(ChatSession)
        .where(ChatSession.user_id == user.id)
        .order_by(ChatSession.created_at.desc())
    )
    return (await db.scalars(stmt)).all()


@router.post("", response_model=SessionOut)
async def create_session(
    payload: SessionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 手动创建新会话，标题为空时使用默认标题
    session = ChatSession(user_id=user.id, title=payload.title or "新会话")
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.get("/{session_id}/messages", response_model=list[MessageOut])
async def get_messages(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 会话归属校验后返回完整消息历史
    session = await db.get(ChatSession, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="会话不存在")
    stmt = (
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.id.asc())
    )
    return (await db.scalars(stmt)).all()


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    # 顾客清空对话：删除自己的会话及其消息、摘要与流程状态
    session = await db.get(ChatSession, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="会话不存在")
    await db.execute(delete(ConversationSummary).where(ConversationSummary.session_id == session_id))
    await db.execute(delete(WorkflowState).where(WorkflowState.session_id == session_id))
    await db.delete(session)
    await db.commit()
    return Response(status_code=204)
