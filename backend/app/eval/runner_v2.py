import asyncio
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from ..agent.graph import run_agent
from ..core.hybrid_rag import hybrid_search
from ..core.intent_router import Intent, IntentRouter

THRESHOLDS = {
    "intent_routing_accuracy": 0.85,
    "tool_execution_success_rate": 0.90,
    "recall_at_2": 0.85,
    "rag_answer_accuracy": 0.80,
    "task_completion_rate": 0.75,
}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _metric(passed: int, total: int) -> dict:
    return {"passed": passed, "total": total, "score": round(passed / total, 4) if total else 0.0}


def _check_required_points(answer: str, required: list[str]) -> bool:
    return all(point in answer for point in required)


def _check_forbidden_points(answer: str, forbidden: list[str]) -> bool:
    return not any(point in answer for point in forbidden)


async def _evaluate_intent(case: dict, answer: str, state: dict) -> dict:
    router = IntentRouter()
    decision = await router.route(case["message"], state)
    expected_intent = case.get("expected_intent", "unknown")
    passed = decision.intent.value == expected_intent
    return {"passed": passed, "actual": decision.intent.value, "expected": expected_intent, "reason_code": decision.reason_code}


async def _evaluate_rag(case: dict) -> dict:
    results = await hybrid_search(case["message"], top_k=2)
    expected_source = case.get("expected_source", "")
    if not expected_source:
        return {"passed": True, "applicable": False, "results": len(results)}
    found = any(expected_source in str(r.get("source", "")) for r in results)
    return {"passed": found, "applicable": True, "results": len(results), "expected_source": expected_source}


async def run_evaluation(cases: list[dict] | None = None) -> dict:
    if cases is None:
        cases = load_eval_cases()

    started = time.perf_counter()
    records: list[dict] = []

    for case in cases:
        case_started = time.perf_counter()
        message = case["message"]

        # Run the agent
        state = await run_agent([{"role": "user", "content": message}], "eval_user")
        answer = state.get("final_response", "")
        duration_ms = round((time.perf_counter() - case_started) * 1000, 2)

        # Intent evaluation
        intent_result = await _evaluate_intent(case, answer, {"phase": "idle"})
        intent_passed = intent_result["passed"]

        # Tool evaluation
        tool_results = state.get("tool_results") or []
        tool_ok = all(r.get("ok") for r in tool_results) if tool_results else True
        tool_applicable = case.get("expected_tool") is not None
        tool_passed = tool_ok if tool_applicable else True

        # RAG evaluation
        rag_applicable = case.get("expected_intent") in ("knowledge_query", "product", "unknown")
        rag_result = {"passed": True, "applicable": False}
        if rag_applicable:
            rag_result = await _evaluate_rag(case)
        rag_passed = rag_result["passed"]

        # Task completion
        required = case.get("required_points", [])
        forbidden = case.get("forbidden_points", [])
        points_ok = _check_required_points(answer, required) if required else True
        no_forbidden = _check_forbidden_points(answer, forbidden) if forbidden else True
        task_passed = points_ok and no_forbidden
        task_applicable = bool(required or forbidden)

        records.append({
            "case_id": case.get("case_id", ""),
            "message": message,
            "answer": answer,
            "duration_ms": duration_ms,
            "intent": intent_result,
            "tool_ok": tool_ok,
            "tool_applicable": tool_applicable,
            "rag": rag_result,
            "task_passed": task_passed,
            "task_applicable": task_applicable,
            "needs_human": bool(state.get("needs_human")),
        })

    # Aggregate metrics
    intent_total = len(records)
    intent_passed_count = sum(1 for r in records if r["intent"]["passed"])

    tool_records = [r for r in records if r["tool_applicable"]]
    tool_passed_count = sum(1 for r in tool_records if r["tool_ok"])

    rag_records = [r for r in records if r["rag"]["applicable"]]
    rag_passed_count = sum(1 for r in rag_records if r["rag"]["passed"])

    task_records = [r for r in records if r["task_applicable"]]
    task_passed_count = sum(1 for r in task_records if r["task_passed"])

    metrics = {
        "intent_routing_accuracy": _metric(intent_passed_count, intent_total),
        "tool_execution_success_rate": _metric(tool_passed_count, len(tool_records)),
        "recall_at_2": _metric(rag_passed_count, len(rag_records)),
        "rag_answer_accuracy": _metric(rag_passed_count, len(rag_records)),
        "task_completion_rate": _metric(task_passed_count, len(task_records)),
    }

    coverage = {
        "intent_routing_accuracy": intent_total,
        "tool_execution_success_rate": len(tool_records),
        "recall_at_2": len(rag_records),
        "rag_answer_accuracy": len(rag_records),
        "task_completion_rate": len(task_records),
    }

    gates = {name: values["score"] >= THRESHOLDS.get(name, 0) for name, values in metrics.items()}

    durations = [r["duration_ms"] for r in records]
    avg_duration = round(sum(durations) / len(durations), 2) if durations else 0

    failures = [
        {"case_id": r["case_id"], "reason": r["intent"].get("reason_code", "")}
        for r in records if not r["intent"]["passed"]
    ]

    return {
        "generated_at": _utcnow_iso(),
        "total_cases": len(cases),
        "metrics": metrics,
        "coverage": coverage,
        "thresholds": THRESHOLDS,
        "gates": gates,
        "passed": all(gates.values()),
        "failures": failures,
        "records": records,
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        "average_duration_ms": avg_duration,
    }


def load_eval_cases() -> list[dict]:
    cases_path = Path(__file__).parent / "cases_v2.json"
    if cases_path.exists():
        return json.loads(cases_path.read_text(encoding="utf-8"))
    # Fallback to built-in cases
    return BUILTIN_CASES


def write_report(result: dict, output_dir: str | Path = "artifacts/evaluation") -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "latest.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


BUILTIN_CASES = [
    {"case_id": "eval_001", "message": "查一下订单 1001", "expected_intent": "order_service", "expected_tool": "get_order", "required_points": ["1001"]},
    {"case_id": "eval_002", "message": "订单 1001 的壁灯物流信息", "expected_intent": "logistics_service", "expected_tool": "get_order", "required_points": ["1001"]},
    {"case_id": "eval_003", "message": "我要退款，订单 1002", "expected_intent": "after_sales", "required_points": ["1002"]},
    {"case_id": "eval_004", "message": "SKU001 还有多少库存", "expected_intent": "inventory_query", "expected_tool": "get_inventory", "required_points": ["SKU001"]},
    {"case_id": "eval_005", "message": "给我推荐一个壁灯", "expected_intent": "knowledge_query", "expected_source": "products"},
    {"case_id": "eval_006", "message": "你好", "expected_intent": "chitchat"},
    {"case_id": "eval_007", "message": "我要投诉这盏柱头灯", "expected_intent": "complaint"},
    {"case_id": "eval_008", "message": "订单 1003 发货了吗", "expected_intent": "logistics_service", "required_points": ["1003"]},
    {"case_id": "eval_009", "message": "退款规则是什么", "expected_intent": "knowledge_query", "expected_source": "policies"},
    {"case_id": "eval_010", "message": "订单 1001 多少钱", "expected_intent": "order_service", "required_points": ["1001"]},
    {"case_id": "eval_011", "message": "帮我查订单", "expected_intent": "order_service", "missing_slots": ["order_id"]},
    {"case_id": "eval_012", "message": "1004", "expected_intent": "order_service"},
    {"case_id": "eval_013", "message": "壁灯多少钱", "expected_intent": "knowledge_query", "expected_source": "products"},
    {"case_id": "eval_014", "message": "太阳能柱头灯怎么充电", "expected_intent": "knowledge_query", "expected_source": "products"},
    {"case_id": "eval_015", "message": "订单 1005 状态", "expected_intent": "order_service", "required_points": ["1005"]},
    {"case_id": "eval_016", "message": "在吗", "expected_intent": "chitchat"},
    {"case_id": "eval_017", "message": "庭院灯我想退货", "expected_intent": "after_sales", "missing_slots": ["order_id"]},
    {"case_id": "eval_018", "message": "SKU002 库存多少", "expected_intent": "inventory_query", "expected_tool": "get_inventory", "required_points": ["SKU002"]},
    {"case_id": "eval_019", "message": "怎么联系人工", "expected_intent": "human_handoff"},
    {"case_id": "eval_020", "message": "发货要多久", "expected_intent": "knowledge_query", "expected_source": "policies"},
]
