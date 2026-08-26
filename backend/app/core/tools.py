# Agent 工具层：注册可被 LLM 调用的工具函数，写操作统一转为人工审批任务
import json
import uuid
from typing import Any

from ..db import async_session_factory
from ..models import HumanTask
from ..rag.store import search_knowledge as rag_search_knowledge
from .doudian_provider import get_provider


async def create_human_task(task_type: str, payload: dict) -> str:
    # 创建 pending 状态的人工任务，任何写操作必须先经过审批
    task_id = str(uuid.uuid4())
    async with async_session_factory() as session:
        session.add(
            HumanTask(
                id=task_id,
                task_type=task_type,
                payload_json=json.dumps(payload, ensure_ascii=False),
                status="pending",
            )
        )
        await session.commit()
    return task_id


async def get_order(order_id: str) -> dict:
    # 订单详情查询，转发给当前 Provider
    return await get_provider().get_order(order_id)


async def list_customer_orders(customer: str) -> list:
    # 按客户查询订单列表，转发给当前 Provider
    return await get_provider().list_orders(customer)


async def get_inventory(sku_id: str) -> int:
    # 查询 SKU 库存，转发给当前 Provider
    return await get_provider().get_inventory(sku_id)


async def process_shipment(order_id: str, company_code: str, logistics_code: str) -> dict:
    # 发货工具只创建审批任务，不直接调用 Provider 写接口
    task_id = await create_human_task(
        "shipment",
        {
            "order_id": order_id,
            "company_code": company_code,
            "logistics_code": logistics_code,
        },
    )
    return {"status": "pending", "task_id": task_id}


async def process_refund(
    return_order_no: str,
    action: str,
    reason: str | None = None,
) -> dict:
    # 退款工具同样只生成 HumanTask，审批通过后才执行真实操作
    task_id = await create_human_task(
        "refund",
        {
            "return_order_no": return_order_no,
            "action": action,
            "reason": reason,
        },
    )
    return {"status": "pending", "task_id": task_id}


async def search_knowledge(query: str) -> list[dict]:
    # 检索知识库，为回答提供可引用的依据片段
    return await rag_search_knowledge(query)


# 工具注册表：工具名 → 处理函数，Agent 只能调用这里注册的工具
_TOOL_HANDLERS: dict[str, Any] = {
    "get_order": get_order,
    "list_customer_orders": list_customer_orders,
    "get_inventory": get_inventory,
    "process_shipment": process_shipment,
    "process_refund": process_refund,
    "search_knowledge": search_knowledge,
}


async def run_tool(name: str, arguments: dict) -> dict:
    # 统一工具执行入口：异常转换为 ToolResult.ok=False，不向 Agent 抛错
    handler = _TOOL_HANDLERS[name]
    try:
        data = await handler(**arguments)
        return {
            "name": name,
            "arguments": arguments,
            "ok": True,
            "data": data,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001 - contract requires ok=False instead of leaking errors
        return {
            "name": name,
            "arguments": arguments,
            "ok": False,
            "data": None,
            "error": str(exc),
        }
