# Grounding 门禁：校验答案中的事实（数字/状态）在依据中是否可溯源，无依据则拒绝输出
import json
import re
from typing import Any


# 中文状态词 → 英文状态枚举的映射，供状态抽取与比对
_STATUS_CN_TO_EN = {
    "已支付": "paid",
    "未支付": "unpaid",
    "已发货": "shipped",
    "已取消": "cancelled",
    "退款中": "refunding",
    "已退款": "refunded",
}

# 全部可识别的英文状态枚举（含中文映射值与补充枚举），作为状态抽取基准
_KNOWN_STATUSES = set(_STATUS_CN_TO_EN.values()) | {
    "pending",
    "completed",
    "closed",
    "success",
}


_PRICE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*元")
_STOCK_RE = re.compile(r"库存\s*(\d+(?:\.\d+)?)")
_ORDER_RE = re.compile(r"(?:订单\s*|ORD-?)\s*(\d{3,})", re.I)


def _numbers(text: str) -> set[str]:
    # 提取独立数字（排除 SKU001 这类字母内数字），用于核对依据里有没有这个数
    found = set()
    for match in re.findall(r"(?<![A-Za-z0-9])\d+(?:\.\d+)?(?![A-Za-z0-9])", text):
        try:
            found.add(str(float(match)))
        except ValueError:
            continue
    return found


def _claim_numbers(text: str) -> set[str]:
    # 只把价格/库存/订单号当硬事实；「能用3年」这种口语数字不拦
    found = set()
    for pattern in (_PRICE_RE, _STOCK_RE, _ORDER_RE):
        for match in pattern.finditer(text or ""):
            try:
                found.add(str(float(match.group(1))))
            except (TypeError, ValueError):
                continue
    return found


def _statuses(text: str) -> set[str]:
    # 从文本中抽取已知状态词（中英文），用于答案与依据的状态比对
    lowered = text.lower()
    found = {status for status in _KNOWN_STATUSES if status in lowered}
    for cn, en in _STATUS_CN_TO_EN.items():
        if cn in text:
            found.add(en)
    return found


def _evidence_text(state: dict[str, Any]) -> str:
    # 汇总工具结果、检索片段与任务编号，作为 Grounding 依据
    parts: list[str] = []
    for result in state.get("tool_results") or []:
        data = result.get("data")
        if data is not None:
            parts.append(json.dumps(data, ensure_ascii=False, default=str))
        if result.get("error"):
            parts.append(str(result["error"]))
    parts.extend(state.get("retrieved_chunks") or [])
    parts.extend(state.get("citations") or [])
    if state.get("human_task_id"):
        parts.append(str(state["human_task_id"]))
    return "\n".join(parts)


def check_grounding(state: dict[str, Any]) -> dict:
    # 答案里的价格/库存/订单号/状态必须能在依据中找到；口语年限等不拦
    answer = state.get("final_response") or ""
    evidence = _evidence_text(state)
    claims = _claim_numbers(answer) | _statuses(answer)
    supported = _numbers(evidence) | _claim_numbers(evidence) | _statuses(evidence)
    missing = claims - supported
    if missing:
        return {
            "ok": False,
            "reason": f"答案中的事实缺少依据: {sorted(missing)[:5]}",
        }
    return {"ok": True, "reason": None}
