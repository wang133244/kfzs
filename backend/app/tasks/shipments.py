# 订单/售后定时与审批任务：审批后执行发货退款写操作，并定时同步平台订单到本地
import asyncio
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from ..core.doudian_provider import get_provider
from ..db import async_session_factory
from ..models import HumanTask, Order
from .celery_app import celery_app


logger = logging.getLogger(__name__)


# 工具函数：取 UTC 当前时间并去掉时区信息，统一数据库时间格式
def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# 审批通过后执行实际写操作：按任务类型调用抖店 Provider 发货或退款（异步实现）
async def run_approved_task(task_id: str) -> None:
    # 审批通过后的写操作：按任务类型调用发货/退款 Provider
    async with async_session_factory() as session:
        task = await session.get(HumanTask, task_id)
        # 幂等：任务不存在或未审批时直接返回，避免误执行
        if task is None or task.status != "approved":
            return
        # 解析审批时保存的任务参数（订单号、物流单号、退款操作等）
        payload = json.loads(task.payload_json or "{}")
        provider = get_provider()
        if task.task_type == "shipment":
            # 发货：物流公司默认顺丰（SF），物流单号来自审批参数
            await provider.create_shipment(
                str(payload.get("order_id", "")),
                str(payload.get("company_code", "SF")),
                str(payload.get("logistics_code", "")),
            )
        elif task.task_type == "refund":
            # 退款：按 action 区分同意退款与拒绝退款
            action = str(payload.get("action") or "refund")
            return_order_no = str(payload.get("return_order_no") or "")
            if action == "reject":
                await provider.reject_refund(
                    return_order_no,
                    str(payload.get("reason") or "客服拒绝退款"),
                )
            else:
                await provider.approve_refund(return_order_no)
        # 记录执行结果，便于审计与问题排查
        logger.info("approved task %s executed", task_id)


# Celery 任务入口：以异步方式执行已审批任务，供审批流程或手动触发
@celery_app.task(name="tasks.execute_approved_task")
def execute_approved_task(task_id: str) -> None:
    asyncio.run(run_approved_task(task_id))


# 订单同步核心逻辑（异步）：拉取平台订单并增量写入本地 orders 表
async def _sync_orders() -> None:
    # 从 Provider 拉取订单并 upsert 到 orders 表
    provider = get_provider()
    orders = await provider.list_orders()
    async with async_session_factory() as session:
        for item in orders:
            # 按 order_id 查重，实现幂等 upsert
            existing = await session.scalar(
                select(Order).where(Order.order_id == item["order_id"])
            )
            if existing is None:
                session.add(
                    Order(
                        order_id=str(item["order_id"]),
                        customer=str(item.get("customer") or ""),
                        product=str(item.get("product") or ""),
                        amount=Decimal(str(item.get("amount") or "0")),
                        status=str(item.get("status") or "unknown"),
                    )
                )
            else:
                # 已存在订单只更新状态与时间，保留其他原始信息
                existing.status = str(item.get("status") or existing.status)
                existing.updated_at = _now()
        # 全部订单处理完后统一提交
        await session.commit()


# Celery 定时任务：周期同步平台订单到本地库（beat 每 5 分钟触发）
@celery_app.task(name="tasks.sync_orders")
def sync_orders() -> None:
    asyncio.run(_sync_orders())
