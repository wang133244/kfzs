import time
from collections import deque
from typing import Any

from langgraph.graph import END, START, StateGraph

from . import nodes
from .state import AgentState


INTENT_LABELS = {
    "order": "订单查询",
    "product": "商品咨询",
    "refund": "退款售后",
    "shipment": "物流发货",
    "inventory": "库存查询",
    "complaint": "投诉处理",
    "smalltalk": "寒暄问候",
    "unknown": "意图识别",
}

_latencies: deque[float] = deque(maxlen=100)


def build_graph():
    graph = StateGraph(AgentState)

    node_names = [
        "classify_intent",
        "route_intent",
        "collect_slots",
        "handle_order",
        "handle_product",
        "handle_refund",
        "handle_shipment",
        "handle_inventory",
        "handle_complaint",
        "handle_smalltalk",
        "handle_unknown",
        "grounding_check",
        "escalate_human",
        "final_answer",
    ]
    for name in node_names:
        func = nodes.route_intent_node if name == "route_intent" else getattr(nodes, name)
        graph.add_node(name, func)

    graph.add_edge(START, "classify_intent")
    graph.add_edge("classify_intent", "route_intent")

    handler_names = [
        "collect_slots",
        "handle_order",
        "handle_product",
        "handle_refund",
        "handle_shipment",
        "handle_inventory",
        "handle_complaint",
        "handle_smalltalk",
        "handle_unknown",
    ]
    route_map = {name: name for name in handler_names + ["escalate_human"]}
    graph.add_conditional_edges("route_intent", nodes.route_intent, route_map)

    for name in handler_names:
        graph.add_edge(name, "grounding_check")

    graph.add_conditional_edges(
        "grounding_check",
        lambda state: "final_answer" if state.get("grounding_passed") else "escalate_human",
        {"final_answer": "final_answer", "escalate_human": "escalate_human"},
    )
    graph.add_edge("escalate_human", "final_answer")
    graph.add_edge("final_answer", END)

    return graph.compile()


agent_graph = build_graph()


def _initial_state(messages: list[dict], user_id: str, session_id: str | None = None) -> dict[str, Any]:
    return {
        "messages": messages,
        "user_id": user_id,
        "session_id": session_id,
        "intent": "unknown",
        "order_id": None,
        "product_query": None,
        "tool_results": [],
        "retrieved_chunks": [],
        "citations": [],
        "needs_human": False,
        "human_task_id": None,
        "final_response": "",
        "iteration": 0,
        "max_iterations": 3,
        "grounding_passed": None,
        "slots": {},
        "missing_slots": [],
        "action": "",
        "next_step": "",
        "reason_code": "",
        "memory_context": {},
        "resolved_query": "",
        "after_sales_preview_id": None,
       "citations_detail": [],
       "safety_blocked": False,
        "relevance_score": 0.0,
        "product_cards": [],
   }


async def run_agent(messages: list[dict], user_id: str, session_id: str | None = None, stream_final: bool = False) -> dict[str, Any]:
    started_at = time.perf_counter()
    try:
        # Load memory context for the session
        if session_id:
            from ..core.memory import memory_service
            ctx = await memory_service.build_context(
                session_id, user_id, messages[-1].get("content", "") if messages else ""
            )
            history = list(ctx.get("recent_messages") or [])
            last = messages[-1] if messages else None
            if last and (not history or history[-1].get("content") != last.get("content")):
                history = history + [last]
            initial = _initial_state(history or messages, user_id, session_id)
            initial["memory_context"] = ctx
        else:
            initial = _initial_state(messages, user_id, session_id)

        initial["stream_final"] = stream_final
        result = await agent_graph.ainvoke(initial)
        return result
    finally:
        _latencies.append(time.perf_counter() - started_at)


def get_avg_latency() -> float:
    if not _latencies:
        return 0.0
    return sum(_latencies) / len(_latencies)


def steps_from_state(state: dict[str, Any]) -> list[dict]:
    intent = state.get("intent") or "unknown"
    steps: list[dict] = [
        {
            "type": "intent",
            "label": INTENT_LABELS.get(intent, "意图识别"),
            "detail": state.get("reason_code") or "",
        }
    ]

    # Show slot extraction info
    slots = state.get("slots") or {}
    if slots:
        detail = ", ".join(f"{k}={v}" for k, v in slots.items())
        steps.append({"type": "slots", "label": "槽位抽取", "detail": detail})

    for result in state.get("tool_results") or []:
        arguments = result.get("arguments") or {}
        detail = ", ".join(f"{key}={value}" for key, value in arguments.items())
        steps.append(
            {
                "type": "tool",
                "label": result.get("name") or "tool",
                "detail": detail,
            }
        )
    if state.get("needs_human"):
        steps.append(
            {
                "type": "status",
                "label": "转人工",
                "detail": state.get("human_task_id"),
            }
        )
    return steps
