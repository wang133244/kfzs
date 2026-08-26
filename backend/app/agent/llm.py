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
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=settings.llm_temperature,
    )


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


def _evidence_for_prompt(state: dict[str, Any]) -> str:
    # 只把工具结果和检索片段交给模型，防止模型编造事实
    parts: list[str] = []
    for result in state.get("tool_results") or []:
        parts.append(
            f"{result.get('name')}: "
            f"{json.dumps(result.get('data'), ensure_ascii=False, default=str)}"
        )
    parts.extend(state.get("retrieved_chunks") or [])
    return "\n".join(parts)


def _llm_prompt(state: dict[str, Any]) -> list[dict[str, str]]:
    # 组装 system/user 消息：system 限定只依据证据作答，user 携带用户消息、意图与工具依据
    messages = state.get("messages") or []
    last_user = str(messages[-1].get("content") or "") if messages else ""
    evidence = _evidence_for_prompt(state)
    memory = state.get("memory_context") or {}
    history = memory.get("recent_messages") or messages
    history_lines = []
    for item in history[-8:]:
        role = "用户" if item.get("role") == "user" else "客服"
        content = str(item.get("content") or "").strip()
        if content:
            history_lines.append(f"{role}：{content[:180]}")
    summary = str(memory.get("summary") or "").strip()
    long_term = memory.get("long_term") or []
    focus = memory.get("workflow_state") or {}
    memory_bits = []
    if summary:
        memory_bits.append(f"会话摘要：{summary[:400]}")
    if focus.get("last_category") or focus.get("last_product_title"):
        memory_bits.append(
            "刚才在聊：" + str(focus.get("last_product_title") or focus.get("last_category"))
        )
    if focus.get("last_order_id"):
        memory_bits.append(f"刚才的订单：{focus.get('last_order_id')}")
    for item in long_term:
        memory_bits.append(f"长期记忆：{item.get('content')}")
    system = (
        "你是星途户外照明专卖店智能客服。只能依据“依据”中的工具结果和知识库片段回答，"
        "只介绍本店灯具，不得编造订单号、金额、库存或政策；使用简体中文，回复简洁专业。"
        "如果用户在追问刚才的商品或订单，结合对话记忆作答，不要装作没有上文。"
    )
    user = (
        f"用户消息：{last_user}\n"
        f"解析后的问题：{state.get('resolved_query') or last_user}\n"
        f"意图：{state.get('intent') or 'unknown'}\n"
        f"最近对话：\n{chr(10).join(history_lines) or '（无）'}\n"
        f"记忆：\n{chr(10).join(memory_bits) or '（无）'}\n\n"
        f"依据：\n{evidence or '（无）'}\n\n"
        "请给出最终回复。"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


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
