import asyncio
import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from ..agent.llm import _llm_client
from ..config import settings
from .safety import mask_sensitive, safe_observation
from .tool_registry import TOOL_REGISTRY, ToolExecutionResult, tool_executor

MAX_REACT_STEPS = 3

READ_TOOL_NAMES = ("get_order", "get_logistics", "get_inventory", "search_knowledge")

TOOL_TO_FUNCTION: dict[str, str] = {
    "get_order": "get_order",
    "get_logistics": "get_logistics",
    "get_inventory": "get_inventory",
    "search_knowledge": "search_knowledge",
}
FUNCTION_TO_TOOL = {v: k for k, v in TOOL_TO_FUNCTION.items()}

TOOL_DESCRIPTIONS = {
    "get_order": "Query one order by order ID. Returns status, product, amount, customer.",
    "get_logistics": "Query logistics for an order by order ID. Returns tracking info.",
    "get_inventory": "Query current stock for a SKU.",
    "search_knowledge": "Search the product knowledge base for product specs and policies.",
}


@dataclass
class ReActRun:
    steps: list[ToolExecutionResult] = field(default_factory=list)
    answer: str | None = None
    stop_reason: str = "completed"
    handoff_requested: bool = False


def _function_definitions(allowed_tools: tuple[str, ...]) -> list[dict[str, Any]]:
    defs: list[dict[str, Any]] = []
    for tool_name in allowed_tools:
        if tool_name not in TOOL_TO_FUNCTION:
            continue
        definition = TOOL_REGISTRY[tool_name]
        func_name = TOOL_TO_FUNCTION[tool_name]
        params: dict[str, Any] = {}
        for param in definition.required_params:
            params[param] = {"type": "string", "description": f"The {param} to query"}
        defs.append({
            "type": "function",
            "function": {
                "name": func_name,
                "description": TOOL_DESCRIPTIONS.get(tool_name, ""),
                "parameters": {"type": "object", "properties": params, "required": list(definition.required_params)},
            },
        })
    return defs


class ControlledReActAgent:
    """Controlled ReAct with function calling, max-step limit, and safe observations."""

    def __init__(self, executor=tool_executor) -> None:
        self.executor = executor

    async def run(
        self,
        run_id: str,
        user_id: str,
        message: str,
        tool_name: str,
        slots: dict[str, str],
    ) -> ReActRun:
        # Direct tool execution when a single tool is determined by routing
        if tool_name and tool_name in TOOL_REGISTRY:
            result = await self.executor.execute(run_id, tool_name, user_id, slots)
            run = ReActRun(steps=[result], answer=self._format_result(result), stop_reason="direct_tool")
            if result.status == "system_error" and result.error_code == "tool_not_registered":
                run.handoff_requested = True
            return run

        # LLM-driven function calling when no specific tool is routed
        if settings.llm_provider.lower() == "mock":
            return ReActRun(answer=None, stop_reason="mock_mode_no_llm")

        allowed = READ_TOOL_NAMES
        messages = [
            {"role": "system", "content": "你是星途户外照明专卖店客服助手。根据用户问题调用合适的工具查询信息，然后给出简洁的中文回复。只介绍本店灯具，不要编造订单号、金额或库存。"},
            {"role": "user", "content": mask_sensitive(message)},
        ]
        run = ReActRun()

        for step in range(MAX_REACT_STEPS):
            try:
                response = await asyncio.to_thread(
                    self._call_llm, messages, _function_definitions(allowed)
                )
            except Exception:
                run.stop_reason = "llm_error"
                run.handoff_requested = True
                return run

            choice = response.choices[0]
            if choice.message.tool_calls:
                for tool_call in choice.message.tool_calls:
                    func_name = tool_call.function.name
                    mapped = FUNCTION_TO_TOOL.get(func_name, func_name)
                    try:
                        call_params = json.loads(tool_call.function.arguments)
                    except (json.JSONDecodeError, TypeError):
                        call_params = {}
                    call_params = {k: str(v) for k, v in {**slots, **call_params}.items()}
                    result = await self.executor.execute(run_id, mapped, user_id, call_params)
                    run.steps.append(result)
                    messages.append(choice.message)
                    observation = safe_observation(result.data or {})
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(observation, ensure_ascii=False),
                    })
                continue

            run.answer = choice.message.content or ""
            run.stop_reason = "llm_final"
            return run

        run.stop_reason = "max_steps"
        run.handoff_requested = True
        return run

    @staticmethod
    def _call_llm(messages: list[dict], tools: list[dict]):
        client = _llm_client()
        return client.invoke(messages, tools=tools)

    @staticmethod
    def _format_result(result: ToolExecutionResult) -> str:
        if not result.ok:
            return f"查询失败：{result.error_message or '请稍后重试'}"
        data = result.data or {}
        if result.tool_name == "get_order":
            return f"订单 {data.get('order_id', '')} 当前状态为{data.get('status', '')}，商品：{data.get('product', '')}，金额：{data.get('amount', '')} 元。"
        if result.tool_name == "get_logistics":
            return f"订单 {data.get('order_id', '')} 物流信息：{data.get('logistics_code', '暂无')}，{data.get('company_code', '')}。"
        if result.tool_name == "get_inventory":
            return f"SKU {data.get('sku_id', '')} 当前库存 {data.get('stock', 0)} 件。"
        if result.tool_name == "search_knowledge":
            results = data.get("results", [])
            if not results:
                return "暂时没有找到相关内容。"
            lines = [f"- {item['text']}" for item in results[:3]]
            return "店里相关信息如下：\n" + "\n".join(lines)
        if result.tool_name == "process_refund":
            return f"您的退款申请已受理，已转人工审核，任务编号：{data.get('task_id', '')}。"
        if result.tool_name == "process_shipment":
            return f"您的发货申请已受理，已转人工审核，任务编号：{data.get('task_id', '')}。"
        return json.dumps(data, ensure_ascii=False)


react_agent = ControlledReActAgent()
