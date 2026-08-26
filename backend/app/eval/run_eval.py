import asyncio
import json
import time
from pathlib import Path

from app.agent.graph import run_agent


CASES_FILE = Path(__file__).with_name("cases.json")


async def run_case(case: dict) -> dict:
    # 单条用例评估：记录意图、工具成功率、拒绝/转人工正确性与延迟
    message = case["message"]
    started = time.perf_counter()
    state = await run_agent([{"role": "user", "content": message}], "eval-user")
    latency = time.perf_counter() - started
    response = state.get("final_response") or ""
    tools = state.get("tool_results") or []
    tool_success = True
    if tools and not case.get("allow_tool_error"):
        tool_success = all(tool.get("ok") for tool in tools)
    must_mention = case.get("must_mention") or ""
    mentioned = (not must_mention) or (must_mention in response)
    refusal_ok = bool(case.get("expect_human")) == bool(state.get("needs_human"))
    if case.get("expect_human") and "无法确认" in response:
        refusal_ok = True
    return {
        "message": message,
        "expected_intent": case["expected_intent"],
        "actual_intent": state.get("intent"),
        "tool_success": tool_success,
        "mention_ok": mentioned,
        "refusal_ok": refusal_ok,
        "latency": latency,
    }


async def main() -> None:
    # 汇总输出 intent_accuracy / tool_success_rate / refusal_accuracy / avg_latency_secs
    cases = json.loads(CASES_FILE.read_text(encoding="utf-8"))
    results = await asyncio.gather(*(run_case(case) for case in cases))
    intent_accuracy = sum(
        r["expected_intent"] == r["actual_intent"] for r in results
    ) / len(results)
    tool_success_rate = sum(r["tool_success"] for r in results) / len(results)
    refusal_accuracy = sum(r["refusal_ok"] for r in results) / len(results)
    avg_latency_secs = sum(r["latency"] for r in results) / len(results)
    metrics = {
        "total_cases": len(results),
        "intent_accuracy": round(intent_accuracy, 4),
        "tool_success_rate": round(tool_success_rate, 4),
        "refusal_accuracy": round(refusal_accuracy, 4),
        "avg_latency_secs": round(avg_latency_secs, 4),
    }
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    for result in results:
        if (
            result["expected_intent"] != result["actual_intent"]
            or not result["refusal_ok"]
            or not result["tool_success"]
            or not result["mention_ok"]
        ):
            print("MISS:", json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
