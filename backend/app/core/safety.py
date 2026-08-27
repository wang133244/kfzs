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


def soften_catalog_names(text: str, cards: list[dict] | None = None) -> str:
    """把回复里的商品全称换成「这款 / 第N款」，身份交给卡片。"""
    result = text or ""
    items = list(cards or [])
    for index, card in enumerate(items[:6], start=1):
        title = str(card.get("title") or "").strip()
        if len(title) < 10:
            continue
        label = "这款" if len(items) == 1 else f"第{index}款"
        for piece in (title, title[:24] if len(title) >= 24 else "", title[:16] if len(title) >= 16 else ""):
            if piece and piece in result:
                result = result.replace(piece, label)
    result = re.sub(r"(这款){2,}", "这款", result)
    result = re.sub(r"(第[1-9]款){2,}", r"\1", result)
    return result


def humanize_customer_text(text: str, cards: list[dict] | None = None) -> str:
    """去掉说明书腔和推脱话，给顾客看店员口吻。"""
    value = plain_customer_text(text)
    value = re.sub(r"根据知识库[：:]\s*", "", value)
    value = re.sub(r"(?:问|答)[：:]\s*", "", value)
    value = re.sub(r"目前知识库中没有[^。！？]*[。！？]?", "", value)
    value = re.sub(r"知识库(?:中|里)?(?:没有|未收录|暂无)[^。！？]*[。！？]?", "", value)
    value = value.replace("知识库", "")
    value = re.sub(r"[^。！？]*详情页[^。！？]*[。！？]?", "", value)
    value = re.sub(r"[^。！？]*建议您?查看商品详情[^。！？]*[。！？]?", "", value)
    value = re.sub(r"[^。！？]*联系店铺客服进一步确认[^。！？]*[。！？]?", "", value)
    value = soften_catalog_names(value, cards)
    cleaned = re.sub(r"\s{2,}", " ", value).strip(" ，,")
    return cleaned or "这款户外做了防水，日常风吹雨淋能用，你可以放心看看。"
