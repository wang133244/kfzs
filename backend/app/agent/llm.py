import asyncio
import json
import re
import time
from typing import Any

from langchain_openai import ChatOpenAI

from ..config import settings


GREETINGS = ("你好", "您好", "hello", "hi", "嗨", "在吗", "在不在", "谢谢")
PRODUCT_KEYWORDS = (
    "柱头灯",
    "壁灯",
    "庭院灯",
    "太阳能",
    "灯具",
    "照明",
    "推荐",
)


def _rule_intent(message: str) -> str:
    # mock 模式规则分类：写操作意图优先，避免“我要退款，订单 1002”被误判为订单查询
    text = message.lower()
    if any(keyword in text for keyword in ("退款", "退货", "售后")):
        return "refund"
    if any(keyword in text for keyword in ("发货", "物流", "快递")):
        return "shipment"
    if "投诉" in text:
        return "complaint"
    if any(keyword in text for keyword in ("库存", "还有货")):
        return "inventory"
    if any(keyword in text for keyword in ("订单", "ord-")):
        return "order"
    if any(keyword in text for keyword in ("商品", "产品", "你们有什么", *PRODUCT_KEYWORDS)):
        return "product"
    if any(greeting in text for greeting in GREETINGS):
        return "smalltalk"
    return "unknown"


def _llm_client() -> ChatOpenAI:
    # OpenAI 兼容客户端：默认指向 DeepSeek，可通过 LLM_BASE_URL 替换任意兼容端点
    cached = getattr(_llm_client, "_cached", None)
    key = (settings.llm_model, settings.llm_api_key, settings.llm_base_url, settings.llm_temperature)
    if cached and cached[0] == key:
        return cached[1]
    client = ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=settings.llm_temperature,
        max_tokens=160,
        timeout=20,
    )
    _llm_client._cached = (key, client)
    return client


def _clip(text: str, limit: int) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    return value[: limit - 1] + "…" if len(value) > limit else value


def _compact_tool(result: dict[str, Any]) -> str:
    data = result.get("data")
    if isinstance(data, dict):
        keep = {
            key: data[key]
            for key in ("order_id", "status", "price", "stock", "sku_id", "logistics_code", "task_id")
            if key in data
        }
        data = keep or data
    return f"{result.get('name')}: {_clip(json.dumps(data, ensure_ascii=False, default=str), 120)}"


def _short_title(title: str) -> str:
    title = (title or "").strip()
    return title[:12] + "…" if len(title) > 14 else title


def _evidence_for_prompt(state: dict[str, Any]) -> str:
    # 只把工具结果和检索片段交给模型，防止模型编造事实
    parts: list[str] = []
    cards = state.get("product_cards") or []
    if cards:
        listing = []
        for index, card in enumerate(cards[:4], start=1):
            title = str(card.get("title") or "")
            price = card.get("price")
            price_text = f"{float(price):.0f}元" if price not in (None, "") else ""
            tags = []
            if "太阳能" in title:
                tags.append("太阳能")
            if "防水" in title or "IP" in title.upper():
                tags.append("防水")
            if "不锈钢" in title:
                tags.append("不锈钢")
            attrs = (" " + " ".join(tags)) if tags else ""
            listing.append(f"{index}.{_short_title(title)}{price_text}{attrs}")
        parts.append("商品：" + "；".join(listing))
    for result in (state.get("tool_results") or [])[:2]:
        parts.append(_compact_tool(result))
    seen = set(parts)
    titles = [str(card.get("title") or "") for card in cards]
    for chunk in (state.get("retrieved_chunks") or [])[:2]:
        clipped = _clip(chunk, 100)
        for title in titles:
            if len(title) >= 10:
                clipped = clipped.replace(title, "这款")
                if len(title) >= 16:
                    clipped = clipped.replace(title[:16], "这款")
        if clipped and clipped not in seen:
            parts.append(clipped)
            seen.add(clipped)
    return "\n".join(parts)


def _llm_prompt(state: dict[str, Any]) -> list[dict[str, str]]:
    # 组装 system/user 消息：system 限定只依据证据作答，user 携带用户消息、意图与工具依据
    messages = state.get("messages") or []
    last_user = str(messages[-1].get("content") or "") if messages else ""
    evidence = _evidence_for_prompt(state)
    memory = state.get("memory_context") or {}
    history = memory.get("recent_messages") or messages
    history_lines = []
    for item in history[-4:]:
        content = str(item.get("content") or "").strip()
        if not content or content == last_user:
            continue
        role = "用户" if item.get("role") == "user" else "客服"
        history_lines.append(f"{role}：{_clip(content, 64)}")
        if len(history_lines) >= 3:
            break
    summary = _clip(str(memory.get("summary") or ""), 80)
    long_term = memory.get("long_term") or []
    focus = memory.get("workflow_state") or {}
    memory_bits = []
    if summary:
        memory_bits.append("摘要：" + summary)
    topic = str(focus.get("last_product_title") or focus.get("last_category") or "").strip()
    if topic:
        memory_bits.append("刚才在聊：" + _clip(topic, 24))
    if focus.get("last_order_id"):
        memory_bits.append(f"订单：{focus.get('last_order_id')}")
    for item in long_term[:1]:
        bit = _clip(str(item.get("content") or ""), 36)
        if bit:
            memory_bits.append("记忆：" + bit)
    system = (
        "你是星途灯具店微信客服，口语短句，最多3句约80字。"
        "只卖柱头灯、户外壁灯、太阳能庭院灯，没有的品类不要提。"
        "往好处说，但不要夸成永不损坏、终身质保。"
        "卡片已给顾客看，你根据编号已经知道用户在说哪一款。"
        "不要复述全称，用「这款」「第一款」「那款」。不要照念依据原句。"
        "价格、库存、订单号必须用依据里的数字，不要编。"
        "问耐用就按防水、不锈钢、太阳能用口语说户外能用，不必报规格。"
        "没问到的型号、售价、物流时效不要主动念。不要markdown。"
        "追问时接着刚才的商品说。"
    )
    lines = [f"用户：{last_user}", f"意图：{state.get('intent') or 'unknown'}"]
    resolved = str(state.get("resolved_query") or "").strip()
    if resolved and resolved != last_user:
        lines.append("问题：" + _clip(resolved, 80))
    if history_lines:
        lines.append("对话：\n" + "\n".join(history_lines))
    if memory_bits:
        lines.append("记忆：\n" + "\n".join(memory_bits))
    lines.append("依据：\n" + (evidence or "无"))
    lines.append("直接回复顾客。")
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n".join(lines)},
    ]


def _llm_intent(message: str) -> str:
    # deepseek 模式：要求模型输出 JSON 意图，解析失败时回退规则分类
    llm = _llm_client()
    prompt = (
        '你是电商客服意图分类器，只输出 JSON，格式为 {"intent": "order|product|refund|'
        'shipment|inventory|complaint|smalltalk|unknown"}。\n'
        f"用户消息: {message}"
    )
    response = llm.invoke(prompt)
    content = str(response.content).strip()
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        return _rule_intent(message)
    try:
        data = json.loads(match.group(0))
        intent = str(data.get("intent", "")).lower()
        allowed = {
            "order",
            "product",
            "refund",
            "shipment",
            "inventory",
            "complaint",
            "smalltalk",
            "unknown",
        }
        return intent if intent in allowed else "unknown"
    except json.JSONDecodeError:
        return _rule_intent(message)


def classify_intent(message: str) -> str:
    # 对外统一入口：mock 不发网络请求，deepseek 走 ChatOpenAI
    if settings.llm_provider.lower() == "mock":
        return _rule_intent(message)
    return _llm_intent(message)


async def generate_chat_response(state: dict[str, Any]) -> str:
    # 真实模式用大模型生成回复；mock 或调用失败时回退规则草稿
    fallback = state.get("final_response") or ""
    if settings.llm_provider.lower() == "mock":
        return fallback
    try:
        response = await asyncio.to_thread(_llm_client().invoke, _llm_prompt(state))
        text = str(response.content).strip()
        return text if text else fallback
    except Exception:
        return fallback

async def generate_chat_response_stream(state: dict[str, Any]):
    # 流式生成最终回复：逐 token yield，首字延迟即 LLM 首 token 延迟
    fallback = state.get("final_response") or ""
    if settings.llm_provider.lower() == "mock":
        if fallback:
            yield fallback
        return
    try:
        async for chunk in _llm_client().astream(_llm_prompt(state)):
            piece = str(chunk.content) if hasattr(chunk, "content") else str(chunk)
            if piece:
                yield piece
    except Exception:
        if fallback:
            yield fallback


async def check_llm() -> dict[str, Any]:
    # 连通性自检：python -m app.agent.llm
    if settings.llm_provider.lower() == "mock":
        return {
            "ok": False,
            "error": "当前 LLM_PROVIDER=mock，请配置 LLM_PROVIDER=deepseek 和 LLM_API_KEY 后重试",
        }
    started = time.perf_counter()
    try:
        response = await asyncio.to_thread(_llm_client().invoke, "请只回复两个字：正常")
        return {
            "ok": True,
            "model": settings.llm_model,
            "latency_secs": round(time.perf_counter() - started, 3),
            "reply": str(response.content).strip(),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


if __name__ == "__main__":
    result = asyncio.run(check_llm())
    print(json.dumps(result, ensure_ascii=False, indent=2))
