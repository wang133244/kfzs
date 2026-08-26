import re
from typing import Any

# Sensitive-field patterns used for desensitization before LLM calls
ORDER_ID = re.compile(r"(?:ORD[-\s]?|订单\s*)\d{3,}", re.I)
PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
TRACKING = re.compile(r"\b[A-Z]{2,8}\d{8,20}\b", re.I)
ADDRESS = re.compile(r"(?:收货地址|地址)[:\uff1a]\s*[^\n]{4,80}")
ID_CARD = re.compile(r"\d{15,18}[0-9Xx]")


def mask_sensitive(text: str) -> str:
    """Replace order numbers, phone numbers, tracking numbers, addresses and ID cards with redaction markers."""
    value = ORDER_ID.sub("[订单号已脱敏]", text)
    value = PHONE.sub("[手机号已脱敏]", value)
    value = TRACKING.sub("[物流单号已脱敏]", value)
    value = ADDRESS.sub("[地址已脱敏]", value)
    return ID_CARD.sub("[证件号已脱敏]", value)


def safe_observation(data: dict[str, Any]) -> dict[str, Any]:
    """Keep only customer-safe fields from tool results, masking any residual sensitive data."""
    allowed = {"status", "product", "amount", "customer", "logistics_code", "company_code", "stock", "order_id", "action", "reason", "task_id"}
    return {key: mask_sensitive(str(value)) for key, value in data.items() if key in allowed}


def validate_customer_answer(question: str, answer: str) -> str | None:
    """Return an error message if the answer leaks sensitive data or is otherwise unsafe."""
    if not answer.strip():
        return "当前暂时无法生成安全回复，请稍后再试。"
    if PHONE.search(answer) or ID_CARD.search(answer) or ADDRESS.search(answer):
        return "当前暂时无法生成安全回复，请稍后再试。"
    return None


def plain_customer_text(text: str) -> str:
    """Strip markdown formatting so the user sees clean natural language."""
    value = text.replace("**", "").replace("__", "").replace("`", "")
    value = re.sub(r"(?m)^\s*(?:[-*?]+|\d+[.)])\s*", "", value)
    value = re.sub(r"(?m)^\s*#{1,6}\s*", "", value)
    value = re.sub(r"\s*\[\d+\]", "", value)
    value = re.sub(r"\s*\n\s*", " ", value)
    return re.sub(r"\s{2,}", " ", value).strip()
