# 后台管理相关 API 路由：人工任务审批、运营统计与库存预警
import logging
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..agent.graph import get_avg_latency
from ..config import settings
from ..db import get_db
from ..models import ChatSession, HumanTask, InventoryAlert, Message, Order, User
from ..core.ws_manager import ws_manager
from ..schemas import (
    AdminCustomerOut,
    AdminOrderOut,
    HumanTaskOut,
    InventoryAlertOut,
    MessageOut,
    StatsOut,
    TaskReviewRequest,
)
from .deps import get_current_staff


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


def _now() -> datetime:
    # 生成无时区信息的 UTC 当前时间，便于与数据库时间字段比较
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _finalize_reply_review(
    task: HumanTask,
    payload: TaskReviewRequest | None,
    db: AsyncSession,
) -> None:
    """回复审核通过：将编辑后的文本存为助手消息，重置转人工状态，推送 WebSocket。"""
    data = json.loads(task.payload_json or "{}")
    session_id = data.get("session_id") or ""
    draft = data.get("draft_response") or ""
    edited = (
        (payload.edited_response if payload and payload.edited_response else draft).strip()
        or draft
    )
    citations = data.get("citations") or []
    customer_user_id = str(data.get("user_id") or "")

    if session_id:
        db.add(
            Message(
                session_id=session_id,
                role="assistant",
                content=edited,
                citations_json=json.dumps(citations, ensure_ascii=False),
                product_cards_json=json.dumps(data.get("product_cards") or [], ensure_ascii=False),
            )
        )
        # 回复已交付，重置转人工状态，顾客轮询将自动停止
        session = await db.get(ChatSession, session_id)
        if session and session.handoff_status == "waiting":
            session.handoff_status = "none"
        await db.commit()

    # WebSocket 即时推送（若顾客在线则即时收到正式回复）
    await ws_manager.send_to_user(
        customer_user_id,
        {"type": "review_reply", "session_id": session_id, "response": edited, "citations": citations},
    )


@router.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
async def get_session_messages_for_staff(
    session_id: str,
    user: User = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    # 审核台读取顾客完整对话，不校验会话归属
    session = await db.get(ChatSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    stmt = (
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.id.asc())
    )
    return (await db.scalars(stmt)).all()


@router.get("/tasks", response_model=list[HumanTaskOut])
async def list_tasks(
    status: str | None = None,
    user: User = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    # 人工任务列表，可按状态筛选，按创建时间倒序
    stmt = select(HumanTask).order_by(HumanTask.created_at.desc())
    if status:
        stmt = stmt.where(HumanTask.status == status)
    return (await db.scalars(stmt)).all()


@router.post("/tasks/{task_id}/approve", response_model=HumanTaskOut)
async def approve_task(
    task_id: str,
    payload: TaskReviewRequest | None = None,
    user: User = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    # 人工审批通过：状态更新后由 Celery（或测试内联）执行真实写操作
    # 任务不存在或已处理过时拒绝审批
    task = await db.get(HumanTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status != "pending":
        raise HTTPException(status_code=400, detail="任务已处理")
    task.status = "approved"
    task.reason = payload.reason if payload else None
    task.reviewed_at = _now()
    await db.commit()
    await db.refresh(task)

    # 回复审核：编辑后的回复落库并发送给顾客，不触发退款/发货任务执行
    if task.task_type == "reply_review":
        await _finalize_reply_review(task, payload, db)
        return task

    if settings.env == "test":
        from ..tasks.shipments import run_approved_task

        await run_approved_task(task_id)
    else:
        try:
            from ..tasks.shipments import execute_approved_task

            execute_approved_task.delay(task_id)
        except Exception as exc:
            logger.warning("celery enqueue failed, running inline: %s", exc)
            from ..tasks.shipments import run_approved_task

            await run_approved_task(task_id)
    return task


@router.post("/tasks/{task_id}/reject", response_model=HumanTaskOut)
async def reject_task(
    task_id: str,
    payload: TaskReviewRequest | None = None,
    user: User = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    # 人工拒绝：记录原因，不触发任何 Provider 写操作
    # 任务不存在或已处理过时拒绝操作
    task = await db.get(HumanTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status != "pending":
        raise HTTPException(status_code=400, detail="任务已处理")
    task.status = "rejected"
    task.reason = payload.reason if payload and payload.reason else "未说明原因"
    task.reviewed_at = _now()
    # 回复审核拒绝：告知顾客已转人工，保持等待状态进入人工客服台
    if task.task_type == "reply_review":
        data = json.loads(task.payload_json or "{}")
        session_id = data.get("session_id") or ""
        if session_id:
            db.add(
                Message(
                    session_id=session_id,
                    role="assistant",
                    content="抱歉，暂时无法回答该问题，已为您转人工客服，请稍候。",
                    citations_json="[]",
                )
            )
            session = await db.get(ChatSession, session_id)
            if session:
                session.handoff_status = "waiting"
    await db.commit()
    await db.refresh(task)
    return task


@router.get("/stats", response_model=StatsOut)
async def get_stats(
    user: User = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
) -> StatsOut:
    # 管理后台统计：今日会话、待处理任务、自动解决率与平均响应延迟
    today_start = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    sessions_today = await db.scalar(
        select(func.count(ChatSession.id)).where(ChatSession.created_at >= today_start)
    )
    pending_tasks = await db.scalar(
        select(func.count(HumanTask.id)).where(HumanTask.status == "pending")
    )
    sessions_today = int(sessions_today or 0)
    pending_tasks = int(pending_tasks or 0)
    resolution_rate = 0.0 if sessions_today == 0 else max(0.0, 1 - pending_tasks / sessions_today)
    return StatsOut(
        today_conversations=sessions_today,
        auto_resolution_rate=round(resolution_rate, 2),
        avg_response_secs=round(get_avg_latency(), 2),
        pending_tasks=pending_tasks,
    )


@router.get("/inventory-alerts", response_model=list[InventoryAlertOut])
async def inventory_alerts(
    user: User = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    # 库存预警列表，按创建时间倒序
    stmt = select(InventoryAlert).order_by(InventoryAlert.created_at.desc())
    return (await db.scalars(stmt)).all()


@router.get("/customers", response_model=list[AdminCustomerOut])
async def list_customers(
    user: User = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
) -> list[AdminCustomerOut]:
    customers = list(
        await db.scalars(select(User).where(User.role == "customer").order_by(User.created_at.desc()))
    )
    result: list[AdminCustomerOut] = []
    for customer in customers:
        session = (
            await db.scalars(
                select(ChatSession)
                .where(ChatSession.user_id == customer.id)
                .order_by(ChatSession.created_at.desc())
            )
        ).first()
        last_message = ""
        status = "none"
        session_id = None
        if session is not None:
            session_id = session.id
            status = session.handoff_status or "none"
            last = (
                await db.scalars(
                    select(Message).where(Message.session_id == session.id).order_by(Message.id.desc())
                )
            ).first()
            last_message = (last.content or "")[:60] if last else ""
        result.append(
            AdminCustomerOut(
                user_id=customer.id,
                username=customer.username,
                avatar_url=customer.avatar_url or "",
                session_id=session_id,
                handoff_status=status,
                last_message=last_message,
                can_chat=status in ("waiting", "active"),
            )
        )
    result.sort(key=lambda item: (0 if item.can_chat else 1, item.username))
    return result


@router.get("/orders", response_model=list[AdminOrderOut])
async def list_admin_orders(
    q: str | None = None,
    user: User = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
) -> list[AdminOrderOut]:
    stmt = (
        select(Order)
        .outerjoin(User, User.id == Order.user_id)
        .order_by(Order.created_at.desc())
    )
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(
                Order.customer.like(like),
                Order.order_id.like(like),
                User.username.like(like),
            )
        )
    orders = list(await db.scalars(stmt))
    return [
        AdminOrderOut(
            order_id=order.order_id,
            customer=order.customer,
            display_name=f"{order.customer} {order.order_id}",
            product=order.product,
            amount=order.amount,
            status=order.status,
            created_at=order.created_at,
            user_id=order.user_id,
        )
        for order in orders
    ]
