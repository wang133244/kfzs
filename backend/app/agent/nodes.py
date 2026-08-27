import re
import time
from typing import Any

from ..core.grounding import check_grounding
from ..core.tools import create_human_task, run_tool
from ..rag.store import keyword_score
from .llm import classify_intent as detect_intent, generate_chat_response

# New modules for enhanced functionality
from ..core.intent_router import IntentRouter, Intent, NextStep
from ..core.tool_registry import tool_executor, ACTION_TO_TOOL, SLOT_LABELS
from ..core.hybrid_rag import hybrid_search_with_answer
from ..config import settings
from ..core.recommend import cards_from_ids, cards_from_result, parse_listed_indexes, recommend_for_user, recommend_products
from ..core.memory import expand_query, extract_category, memory_service
from ..core.safety import humanize_customer_text, mask_sensitive, soften_catalog_names, validate_customer_answer

ORDER_ID_PATTERN = re.compile(r"(?:ORD-|订单\s*)(\d{3,})")
SKU_PATTERN = re.compile(r"(SKU-\d+|SKU\d+)", re.IGNORECASE)

STATUS_CN = {
    "paid": "已支付",
    "unpaid": "未支付",
    "shipped": "已发货",
    "cancelled": "已取消",
    "refunding": "退款中",
    "refunded": "已退款",
}

INTENT_HANDLERS = {
    "order": "handle_order",
    "product": "handle_product",
    "refund": "handle_refund",
    "shipment": "handle_shipment",
    "inventory": "handle_inventory",
    "complaint": "handle_complaint",
    "smalltalk": "handle_smalltalk",
    "unknown": "handle_unknown",
}

# Map new Intent enum values to old intent strings for backward compat
INTENT_MAP = {
    Intent.CHITCHAT: "smalltalk",
    Intent.KNOWLEDGE_QUERY: "product",
    Intent.ORDER_SERVICE: "order",
    Intent.LOGISTICS_SERVICE: "shipment",
    Intent.INVENTORY_QUERY: "inventory",
    Intent.AFTER_SALES: "refund",
    Intent.COMPLAINT: "complaint",
    Intent.HUMAN_HANDOFF: "complaint",
    Intent.UNKNOWN: "unknown",
}

_intent_router = IntentRouter()

OFFTOPIC_ASK = "抱歉小助手无法理解您的意思，是否需要转人工"
_POLICY_ONLY_HINTS = ("营业", "工作时间", "包邮", "运费", "发票", "开票", "怎么买", "钱包", "退货", "退款", "售后", "流程")
_PRODUCT_HINTS = (
    "柱头灯", "壁灯", "庭院灯", "灯具", "灯", "推荐", "商品", "多少钱",
    "防水", "安装", "接线", "充电", "色温", "ip65", "太阳能",
)


def _should_attach_cards(message: str) -> bool:
    if any(hint in message for hint in _PRODUCT_HINTS):
        return True
    if any(hint in message for hint in _POLICY_ONLY_HINTS):
        return False
    return True


def _last_message(state: dict[str, Any]) -> str:
    messages = state.get("messages") or []
    if not messages:
        return ""
    return str(messages[-1].get("content") or "")


def _status_cn(status: str) -> str:
    return STATUS_CN.get(status, status)


def _tool_result_to_dict(result) -> dict:
    """Convert ToolExecutionResult to the legacy tool result dict format."""
    return {
        "name": result.tool_name,
        "arguments": {},
        "ok": result.ok,
        "data": result.data,
        "error": result.error_message,
    }


def _clip_text(text: str, limit: int = 100) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    return value[: limit - 1] + "…" if len(value) > limit else value


def _card_listing(cards: list[dict]) -> str:
    items = []
    for card in cards[:4]:
        title = str(card.get("title") or "")[:16]
        price = card.get("price")
        price_text = f"{float(price):.0f}元" if price not in (None, "") else ""
        items.append(f"{title}{price_text}".strip())
    return "；".join(items)


def _recommend_intro(strategy: str, listing: str) -> str:
    # 卡片会单独展示，回复里不拼全称，避免下一轮 prompt 膨胀
    if strategy == "history":
        return "根据您的购买记录挑了几款，点卡片看详情。"
    if strategy == "random":
        return "店里这几款可以看看，点卡片看详情。"
    return "为您推荐这几款在售商品，点卡片看详情。"


def _build_product_cards(
    message: str,
    limit: int | None = None,
    purchased_ids: set[str] | None = None,
    purchased_categories: list[str] | None = None,
) -> list[dict]:
    result = recommend_products(
        message,
        purchased_ids=purchased_ids,
        purchased_categories=purchased_categories,
        limit=limit,
    )
    return cards_from_result(result)


def _spoken_product_reply(message: str, answer: str, cards: list[dict], rec=None) -> str:
    if not cards:
        return answer
    if any(word in message for word in ("多少钱", "价格", "售价")):
        bits = []
        for index, card in enumerate(cards[:3], start=1):
            price = card.get("price")
            if price not in (None, ""):
                label = "这款" if len(cards) == 1 else f"第{index}款"
                bits.append(f"{label}{float(price):.0f}元")
        return "，".join(bits) + "，点卡片看详情。" if bits else "价格在卡片上。"
    if any(word in message for word in ("耐用", "结实", "质量", "好用吗", "对比", "哪个好", "好看", "防水吗")):
        label = "这款" if len(cards) == 1 else "这几款"
        return f"{label}户外做了防水，日常风吹雨淋能用。"
    if any(word in message for word in ("推荐", "有什么", "看看", "哪款", "哪种")):
        strategy = rec.strategy if rec is not None else "need"
        return _recommend_intro(strategy, "")
    spoken = soften_catalog_names(answer, cards)
    for card in cards:
        title = str(card.get("title") or "")
        if len(title) > 16 and title[:16] in spoken:
            return "这款可以看看，点卡片看详情。"
    return spoken


async def _offer_handoff(state: dict[str, Any], message: str) -> dict[str, Any]:
    session_id = state.get("session_id")
    if session_id:
        await memory_service.save_workflow_state(
            session_id,
            str(state.get("user_id") or ""),
            phase="awaiting_handoff_confirm",
            action="confirm_handoff",
        )
    return {
        "final_response": OFFTOPIC_ASK,
        "retrieved_chunks": [OFFTOPIC_ASK],
        "grounding_passed": True,
        "needs_human": False,
    }


async def _maybe_remember(state: dict[str, Any], reply: str) -> str:
    message = _last_message(state)
    if "记住" not in message:
        return reply
    record = await memory_service.capture_explicit_memory(str(state.get("user_id") or ""), message)
    if not record:
        return reply
    return f"好的，已记住：{record['content']}。{reply}"


async def _remember_product_focus(state: dict[str, Any], message: str, cards: list[dict]) -> None:
    session_id = state.get("session_id")
    if not session_id:
        return
    card = cards[0] if cards else {}
    category = str(card.get("category") or extract_category(message) or "")
    await memory_service.save_dialog_focus(
        session_id,
        str(state.get("user_id") or ""),
        last_intent="product",
        last_product_query=message,
        last_category=category,
        last_product_title=str(card.get("title") or ""),
        last_product_id=str(card.get("product_id") or ""),
        last_product_ids=",".join(
            str(item.get("product_id") or "") for item in cards if item.get("product_id")
        ),
    )
    if category:
        await memory_service.remember_interest(str(state.get("user_id") or ""), category)


async def classify_intent(state: dict[str, Any]) -> dict[str, Any]:
    message = _last_message(state)
    iteration = int(state.get("iteration") or 0) + 1
    max_iterations = int(state.get("max_iterations") or 3)
    if iteration > max_iterations:
        task_id = await create_human_task(
            "complaint",
            {"message": message, "reason": "max iterations exceeded"},
        )
        return {
            "iteration": iteration,
            "needs_human": True,
            "human_task_id": task_id,
            "final_response": "处理次数超过上限，已为您转人工核实。",
        }

    # Use enhanced intent router with slot extraction and workflow state
    wf_state = state.get("memory_context", {}).get("workflow_state", {"phase": "idle"})
    try:
        decision = await _intent_router.route(message, wf_state)
        intent = INTENT_MAP.get(decision.intent, "unknown")
        session_id = state.get("session_id")
        resolved_query = expand_query(message, wf_state)
        if (
            session_id
            and wf_state.get("phase") == "awaiting_handoff_confirm"
            and decision.reason_code not in ("handoff_confirmed", "handoff_declined", "offtopic_keyword")
        ):
            await memory_service.clear_workflow_state(session_id)
        return {
            "iteration": iteration,
            "intent": intent,
            "slots": decision.slots,
            "missing_slots": decision.missing_slots,
            "action": decision.action,
            "next_step": decision.next_step.value,
            "reason_code": decision.reason_code,
            "resolved_query": resolved_query,
        }
    except Exception:
        # Fallback to legacy classification
        return {"iteration": iteration, "intent": detect_intent(message), "slots": {}, "missing_slots": [], "action": "", "next_step": "", "reason_code": "fallback"}


def route_intent(state: dict[str, Any]) -> str:
    if state.get("needs_human"):
        return "escalate_human"
    # If slots are missing, go to collect_slots first
    if state.get("missing_slots") and state.get("intent") in ("order", "refund", "shipment", "inventory"):
        return "collect_slots"
    return INTENT_HANDLERS.get(state.get("intent"), "handle_unknown")


async def route_intent_node(state: dict[str, Any]) -> dict[str, Any]:
    return {"intent": state.get("intent") or "unknown"}


async def collect_slots(state: dict[str, Any]) -> dict[str, Any]:
    """Ask the user for missing required slots and save workflow state."""
    message = _last_message(state)
    missing = state.get("missing_slots") or []
    if not missing:
        return {}
    labels = [SLOT_LABELS.get(slot, slot) for slot in missing]
    answer = "请补充以下信息：{}。".format("、".join(dict.fromkeys(labels)))
    session_id = state.get("session_id")
    if session_id:
        await memory_service.save_workflow_state(
            session_id, state.get("user_id", ""),
            phase="awaiting_order_id",
            action=state.get("action", "order_query"),
        )
    return {"final_response": answer, "grounding_passed": True}


async def handle_order(state: dict[str, Any]) -> dict[str, Any]:
    message = _last_message(state)
    slots = state.get("slots") or {}
    order_id = slots.get("order_id")
    match = ORDER_ID_PATTERN.search(message)
    if not order_id and match:
        order_id = match.group(1)
    if not order_id:
        return {"final_response": "请提供订单号，我才能为您查询。"}

    result = await tool_executor.execute("run_0", "get_order", str(state.get("user_id", "")), {"order_id": order_id})
    if not result.ok:
        return {
            "order_id": order_id,
            "tool_results": [_tool_result_to_dict(result)],
            "final_response": f"很抱歉，未查询到订单 {order_id} 的信息。",
        }
    order = result.data or {}
    response = (
        f"订单 {order_id} 当前状态为{_status_cn(order.get('status', ''))}，"
        f"商品：{order.get('product', '')}，金额：{order.get('amount', '')} 元，客户：{order.get('customer', '')}。"
    )
    session_id = state.get("session_id")
    if session_id:
        await memory_service.save_dialog_focus(
            session_id,
            str(state.get("user_id") or ""),
            last_intent="order",
            last_order_id=str(order_id),
        )
    return {
        "order_id": order_id,
        "tool_results": [_tool_result_to_dict(result)],
        "final_response": response,
    }


async def handle_refund(state: dict[str, Any]) -> dict[str, Any]:
    message = _last_message(state)
    slots = state.get("slots") or {}
    order_id = slots.get("order_id")
    match = ORDER_ID_PATTERN.search(message)
    if not order_id and match:
        order_id = match.group(1)
    if not order_id:
        order_id = "待确认"

    result = await run_tool(
        "process_refund",
        {"return_order_no": order_id, "action": "refund", "reason": message},
    )
    if not result["ok"]:
        return {
            "tool_results": [result],
            "final_response": "退款申请提交失败，请稍后重试或联系人工客服。",
        }
    task_id = result["data"]["task_id"]

    # Save workflow state for multi-turn confirmation
    session_id = state.get("session_id")
    if session_id and order_id != "待确认":
        await memory_service.save_workflow_state(
            session_id, str(state.get("user_id", "")),
            phase="awaiting_after_sales_confirmation",
            order_id=order_id, action="refund_only",
        )

    return {
        "order_id": order_id,
        "tool_results": [result],
        "needs_human": True,
        "human_task_id": task_id,
        "final_response": f"您的退款申请已受理，已转人工审核，任务编号：{task_id}。",
    }


async def handle_shipment(state: dict[str, Any]) -> dict[str, Any]:
    message = _last_message(state)
    slots = state.get("slots") or {}
    order_id = slots.get("order_id")
    match = ORDER_ID_PATTERN.search(message)
    if not order_id and match:
        order_id = match.group(1)

    if not order_id and any(keyword in message for keyword in ("政策", "规则", "多久", "时间")):
        answer, citations, _relevance = await hybrid_search_with_answer(message)
        if answer != "暂时没有相关内容。":
            return {
                "retrieved_chunks": [c.get("text", "") for c in citations],
                "citations": sorted({c.get("source", "unknown") for c in citations}),
                "citations_detail": citations,
                "final_response": answer,
            }

    ship_request = "发货" in message and not any(
        keyword in message for keyword in ("政策", "多久", "时间", "规则", "怎么")
    )
    if ship_request:
        company_code = "SF"
        logistics_code = f"SF{int(time.time() * 1000)}"
        result = await run_tool(
            "process_shipment",
            {"order_id": order_id or "待确认", "company_code": company_code, "logistics_code": logistics_code},
        )
        if not result["ok"]:
            return {
                "tool_results": [result],
                "final_response": "发货申请提交失败，请稍后重试或联系人工客服。",
            }
        task_id = result["data"]["task_id"]
        return {
            "order_id": order_id,
            "tool_results": [result],
            "needs_human": True,
            "human_task_id": task_id,
            "final_response": f"您的发货申请已受理，已转人工审核，任务编号：{task_id}。",
        }

    if not order_id:
        return {"final_response": "请提供订单号，我才能为您查询物流信息。"}
    result = await tool_executor.execute("run_0", "get_order", str(state.get("user_id", "")), {"order_id": order_id})
    if not result.ok:
        return {
            "order_id": order_id,
            "tool_results": [_tool_result_to_dict(result)],
            "final_response": f"很抱歉，未查询到订单 {order_id} 的信息。",
        }
    order = result.data or {}
    if order.get("status") == "shipped":
        logistics = order.get("logistics_code") or "待更新"
        response = f"订单 {order_id} 已发货，物流单号：{logistics}。"
    else:
        response = f"订单 {order_id} 当前状态为{_status_cn(order.get('status', ''))}，暂未发货。"
    return {
        "order_id": order_id,
        "tool_results": [_tool_result_to_dict(result)],
        "final_response": response,
    }


async def handle_product(state: dict[str, Any]) -> dict[str, Any]:
    raw_message = _last_message(state)
    message = state.get("resolved_query") or raw_message
    answer, citations, relevance_score = await hybrid_search_with_answer(message, top_k=2)
    wf = state.get("memory_context", {}).get("workflow_state") or {}
    last_ids = [item for item in str(wf.get("last_product_ids") or "").split(",") if item]
    last_cards = cards_from_ids(last_ids)
    indexes = parse_listed_indexes(raw_message)
    picked = []
    for index in indexes:
        if 1 <= index <= len(last_cards):
            picked.append(last_cards[index - 1])
    rec = None
    keep_last_ids = False
    if picked:
        product_cards = picked
        keep_last_ids = True
    else:
        rec = await recommend_for_user(message, str(state.get("user_id") or ""))
        product_cards = cards_from_result(rec) if _should_attach_cards(raw_message) else []
    listing = _card_listing(product_cards)
    if (answer == "暂时没有相关内容。" or not citations) and not product_cards:
        return await _offer_handoff(state, message)
    if (answer == "暂时没有相关内容。" or not citations) and product_cards:
        intro_strategy = rec.strategy if rec is not None else "need"
        answer = _recommend_intro(intro_strategy, listing)
        citations = [{"source": "products.md", "text": listing, "score": 1.0}]
        relevance_score = max(relevance_score, 0.5)
    chunks = [_clip_text(c.get("text", "")) for c in citations[:2] if c.get("text")]
    sources = sorted({c.get("source", "unknown") for c in citations})
    if listing:
        chunks.append(listing)
    # 已命中在售商品时直接回复并附卡片，不再因低相关把推荐转审核
    if relevance_score < settings.relevance_threshold and not product_cards:
        return await _offer_handoff(state, message)
    if keep_last_ids:
        await _remember_product_focus(state, raw_message, last_cards)
    else:
        await _remember_product_focus(state, message, product_cards)
    reply = _spoken_product_reply(raw_message, answer, product_cards, rec)
    return {
        "product_query": message,
        "retrieved_chunks": chunks,
        "citations": sources,
        "citations_detail": citations,
        "relevance_score": relevance_score,
        "product_cards": product_cards,
        "final_response": await _maybe_remember(state, reply),
    }


async def handle_inventory(state: dict[str, Any]) -> dict[str, Any]:
    message = _last_message(state)
    slots = state.get("slots") or {}
    sku_id = slots.get("sku_id")
    match = SKU_PATTERN.search(message)
    if not sku_id and match:
        sku_id = match.group(1).upper()
    if not sku_id:
        sku_id = "SKU001"
    result = await tool_executor.execute("run_0", "get_inventory", str(state.get("user_id", "")), {"sku_id": sku_id})
    if not result.ok:
        return {
            "tool_results": [_tool_result_to_dict(result)],
            "final_response": f"很抱歉，SKU {sku_id} 的库存信息暂时无法确认。",
        }
    stock = (result.data or {}).get("stock", 0)
    return {
        "tool_results": [_tool_result_to_dict(result)],
        "final_response": f"SKU {sku_id} 当前库存 {stock} 件。",
    }


async def handle_complaint(state: dict[str, Any]) -> dict[str, Any]:
    message = _last_message(state)
    task_id = await create_human_task("complaint", {"message": message})
    session_id = state.get("session_id")
    if session_id:
        await memory_service.clear_workflow_state(session_id)
    handoff = state.get("action") in ("human_handoff", "confirm_handoff") or state.get("reason_code") in (
        "human_handoff_keyword",
        "handoff_confirmed",
    )
    if handoff:
        reply = "好的，已为您转接人工客服，请稍候。"
    else:
        reply = f"您的投诉已受理，已转人工处理，工单编号：{task_id}。"
    return {
        "needs_human": True,
        "human_task_id": task_id,
        "final_response": reply,
    }


async def handle_smalltalk(state: dict[str, Any]) -> dict[str, Any]:
    message = _last_message(state)
    wf = state.get("memory_context", {}).get("workflow_state") or {}
    if state.get("action") == "cancel_handoff":
        session_id = state.get("session_id")
        if session_id:
            await memory_service.clear_workflow_state(session_id)
        return {
            "final_response": "好的，那请继续告诉我您想咨询的灯具、订单或售后问题。",
            "needs_human": False,
        }
    topic = str(wf.get("last_product_title") or wf.get("last_category") or "").strip()
    order_id = str(wf.get("last_order_id") or "").strip()
    if state.get("action") == "recall_memory" or "记得" in message:
        parts = [item for item in (topic, f"订单 {order_id}" if order_id else "") if item]
        if parts:
            return {
                "final_response": f"记得，您刚在咨询{'、'.join(parts)}。需要继续了解价格、安装还是物流？",
            }
        return {
            "final_response": "我还没有记下您刚才的商品或订单，您可以直接告诉我灯具名称或订单号。",
        }
    if "谢谢" in message:
        extra = f"您刚才看的是{topic}，" if topic else ""
        return {
            "final_response": f"不客气。{extra}还可以继续问我柱头灯、壁灯、庭院灯，或查询订单、物流和售后。",
        }
    if topic:
        if wf.get("last_product_query") or wf.get("last_product_title"):
            return {
                "final_response": (
                    f"您好，您刚才在看{topic}，可以继续问价格、防水或安装；"
                    "也可以问我柱头灯、壁灯、庭院灯，或查询订单和售后。"
                ),
            }
        return {
            "final_response": (
                f"您好，您之前关注过{topic}，需要我继续介绍吗？"
                "也可以问柱头灯、壁灯、庭院灯，或查询订单和售后。"
            ),
        }
    return {
        "final_response": "你好，星途灯具店的。店里是户外柱头灯、壁灯、庭院灯，想看哪类跟我说。",
    }


async def handle_unknown(state: dict[str, Any]) -> dict[str, Any]:
    message = _last_message(state)
    if state.get("action") == "offtopic" or state.get("reason_code") == "offtopic_keyword":
        return await _offer_handoff(state, message)
    answer, citations, relevance_score = await hybrid_search_with_answer(message)
    if answer != "暂时没有相关内容。" and citations and relevance_score >= settings.relevance_threshold:
        chunks = [c.get("text", "") for c in citations]
        sources = sorted({c.get("source", "unknown") for c in citations})
        return {
            "retrieved_chunks": chunks,
            "citations": sources,
            "citations_detail": citations,
            "relevance_score": relevance_score,
            "final_response": answer,
        }
    return await _offer_handoff(state, message)


async def grounding_check(state: dict[str, Any]) -> dict[str, Any]:
    check = check_grounding(state)
    if check["ok"]:
        return {"grounding_passed": True}
    cards = state.get("product_cards") or []
    if cards:
        listing = _card_listing(cards)
        answer = f"为您推荐这几款在售商品：{listing}。"
        chunks = list(state.get("retrieved_chunks") or [])
        chunks.append(listing)
        retry = check_grounding({**state, "final_response": answer, "retrieved_chunks": chunks})
        if retry["ok"]:
            return {
                "grounding_passed": True,
                "final_response": answer,
                "retrieved_chunks": chunks,
            }
    return {
        "grounding_passed": False,
        "needs_human": True,
        "final_response": "我暂时无法确认，已为您转人工核实。",
    }


async def escalate_human(state: dict[str, Any]) -> dict[str, Any]:
    if state.get("human_task_id"):
        return {"needs_human": True}
    task_id = await create_human_task(
        "complaint",
        {"message": _last_message(state), "reason": "grounding check failed"},
    )
    return {"needs_human": True, "human_task_id": task_id}


_NO_POLISH_ACTIONS = {"offtopic", "cancel_handoff", "confirm_handoff", "human_handoff", "casual_chat"}


def should_skip_polish(state: dict[str, Any]) -> bool:
    if state.get("intent") in ("chitchat", "smalltalk"):
        return True
    if (state.get("final_response") or "") == OFFTOPIC_ASK:
        return True
    if state.get("action") in _NO_POLISH_ACTIONS:
        return True
    if state.get("reason_code") in (
        "chitchat",
        "offtopic_keyword",
        "offline_fallback",
        "handoff_declined",
        "handoff_confirmed",
        "refund_policy_keyword",
    ):
        return True
    return False


async def final_answer(state: dict[str, Any]) -> dict[str, Any]:
    response = state.get("final_response") or "我暂时无法确认，已为您转人工核实。"
    # WS 流式路径跳过同步 LLM 润色，由 chat_ws 逐 token 推送
    if not state.get("needs_human") and not state.get("stream_final") and not should_skip_polish(state):
        generated = await generate_chat_response(state)
        if generated and generated != response:
            grounded = check_grounding({**state, "final_response": generated})
            if grounded["ok"]:
                response = generated

    # Safety validation: check for sensitive data leakage
    safety_issue = validate_customer_answer("", response)
    if safety_issue and not state.get("needs_human"):
        response = safety_issue
        return {
            "final_response": response,
            "citations": sorted(set(state.get("citations") or [])),
            "needs_human": True,
            "safety_blocked": True,
        }

    citations = sorted(set(state.get("citations") or []))
    return {
        "final_response": humanize_customer_text(response, state.get("product_cards") or []),
        "citations": citations,
        "needs_human": bool(state.get("needs_human")),
        "safety_blocked": False,
        "relevance_score": float(state.get("relevance_score") or 0.0),
        "product_cards": state.get("product_cards") or [],
    }
