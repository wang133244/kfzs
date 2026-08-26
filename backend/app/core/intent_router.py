import asyncio
import json
import re
from dataclasses import dataclass, field
from enum import Enum

from ..agent.llm import _llm_client
from ..config import settings


class Intent(str, Enum):
    CHITCHAT = "chitchat"
    KNOWLEDGE_QUERY = "knowledge_query"
    ORDER_SERVICE = "order_service"
    LOGISTICS_SERVICE = "logistics_service"
    INVENTORY_QUERY = "inventory_query"
    AFTER_SALES = "after_sales"
    COMPLAINT = "complaint"
    HUMAN_HANDOFF = "human_handoff"
    UNKNOWN = "unknown"


class NextStep(str, Enum):
    DIRECT_REPLY = "direct_reply"
    RETRIEVE_KNOWLEDGE = "retrieve_knowledge"
    CALL_TOOL = "call_tool"
    COLLECT_SLOTS = "collect_slots"
    COLLECT_CLARIFICATION = "collect_clarification"
    PREPARE_AFTER_SALES = "prepare_after_sales"
    TRANSFER_TO_HUMAN = "transfer_to_human"


@dataclass
class RouteDecision:
    intent: Intent
    action: str
    slots: dict[str, str] = field(default_factory=dict)
    missing_slots: list[str] = field(default_factory=list)
    risk_level: str = "low"
    next_step: NextStep = NextStep.DIRECT_REPLY
    reason_code: str = ""


ORDER_PATTERN = re.compile(r"(?:ORD[-\s]?|订单\s*)(\d{3,})", re.I)
SKU_PATTERN = re.compile(r"(SKU-?\d+)", re.I)

KNOWLEDGE_KEYWORDS = (
    "商品", "产品", "规格", "参数", "你们有什么", "推荐", "柱头灯", "壁灯", "庭院灯",
    "太阳能", "灯具", "照明", "防水", "政策", "规则", "多久", "时间", "包邮", "运费",
    "发票", "开票", "保修", "安装", "接线", "充电", "色温", "无理由", "营业", "工作时间",
    "怎么买", "下单", "钱包", "阴天", "ip65", "IP65",
)
POLICY_QUESTION_HINTS = ("流程", "规则", "政策", "怎么退", "如何退", "支持吗", "可以退吗")
REFUND_KEYWORDS = ("退款", "退货", "售后", "退钱")
LOGISTICS_KEYWORDS = ("发货", "物流", "快递", "运单", "到哪")
INVENTORY_KEYWORDS = ("库存", "有货", "还有货", "缺货")
COMPLAINT_KEYWORDS = ("投诉", "举报", "差评", "曝光")
HUMAN_HANDOFF_KEYWORDS = (
    "转人工", "人工客服", "找人工", "真人", "人工服务", "接线员",
    "转接人工", "找客服", "联系人工", "human", "agent",
)
GREETINGS = ("你好", "您好", "hello", "hi", "嗨", "在吗", "在不在", "谢谢")
OFFTOPIC_KEYWORDS = (
    "天气", "下雨", "股票", "基金", "彩票", "足球", "篮球", "世界杯", "新闻",
    "做饭", "菜谱", "高考", "作业", "编程", "python", "笑话", "唱歌", "星座", "算命",
)
HANDOFF_YES = {
    "是", "好", "要", "行", "可以", "需要", "确定", "确认", "嗯", "对",
    "好的", "是的", "要的", "转", "转吧", "转一下", "好呀", "行吧", "yes", "ok", "okay",
}
HANDOFF_NO = ("不用", "不需要", "不必", "不要", "算了", "取消", "不转", "不用了", "否")
EXPLICIT_HANDOFF_ACTIONS = {"human_handoff", "confirm_handoff"}
EXPLICIT_HANDOFF_REASONS = {"human_handoff_keyword", "handoff_confirmed"}


def is_handoff_affirmative(text: str) -> bool:
    """用户是否明确同意/要求转人工。新问题即使很短，只要不是肯定词就不算确认。"""
    raw = (text or "").strip()
    if not raw:
        return False
    if any(w in raw for w in HANDOFF_NO):
        return False
    compact = re.sub(r"[\s。！？!?，,、]", "", raw).lower()
    if compact in HANDOFF_YES:
        return True
    return any(w in raw for w in HUMAN_HANDOFF_KEYWORDS)


def is_explicit_handoff(state: dict) -> bool:
    return (
        str(state.get("action") or "") in EXPLICIT_HANDOFF_ACTIONS
        or str(state.get("reason_code") or "") in EXPLICIT_HANDOFF_REASONS
    )


class IntentRouter:
    """Rule-first + LLM-fallback intent router with slot extraction."""

    @staticmethod
    def extract_slots(text: str) -> dict[str, str]:
        slots: dict[str, str] = {}
        order_match = ORDER_PATTERN.search(text)
        if order_match:
            slots["order_id"] = order_match.group(1)
        sku_match = SKU_PATTERN.search(text)
        if sku_match:
            slots["sku_id"] = sku_match.group(1).upper()
        return slots

    @staticmethod
    def from_state(text: str, state: dict[str, str], slots: dict[str, str]) -> RouteDecision | None:
        phase = state.get("phase", "idle")
        if phase == "awaiting_order_id":
            order_match = ORDER_PATTERN.search(text) or re.search(r"\b\d{3,}\b", text)
            if order_match:
                oid = order_match.group(1) if order_match.lastindex else order_match.group(0)
                action = state.get("action", "order_query")
                return RouteDecision(
                    intent=Intent.AFTER_SALES if "refund" in action else Intent.ORDER_SERVICE,
                    action=action, slots={"order_id": oid, **slots},
                    next_step=NextStep.CALL_TOOL, reason_code="slot_from_state",
                )
            return RouteDecision(
                intent=Intent.ORDER_SERVICE, action="order_query", slots=slots,
                missing_slots=["order_id"], next_step=NextStep.COLLECT_SLOTS,
                reason_code="still_awaiting_order_id",
            )
        if phase == "awaiting_after_sales_confirmation":
            if any(w in text for w in ("确认", "同意", "好", "可以", "确定", "提交")):
                return RouteDecision(
                    intent=Intent.AFTER_SALES, action=state.get("action", "refund_only"),
                    slots={"order_id": state.get("order_id", "")}, next_step=NextStep.PREPARE_AFTER_SALES,
                    reason_code="after_sales_confirmed",
                )
            if any(w in text for w in ("取消", "不要", "算了", "放弃")):
                return RouteDecision(
                    intent=Intent.AFTER_SALES, action="cancel", slots=slots,
                    next_step=NextStep.DIRECT_REPLY, reason_code="after_sales_cancelled",
                )
        if phase == "awaiting_handoff_confirm":
            compact = re.sub(r"[\s。！？!?，,、]", "", text).lower()
            if any(w in text for w in HANDOFF_NO):
                return RouteDecision(
                    Intent.CHITCHAT, "cancel_handoff", slots,
                    next_step=NextStep.DIRECT_REPLY, reason_code="handoff_declined",
                )
            if compact in HANDOFF_YES or any(w in text for w in HUMAN_HANDOFF_KEYWORDS):
                return RouteDecision(
                    Intent.HUMAN_HANDOFF, "confirm_handoff", slots,
                    next_step=NextStep.TRANSFER_TO_HUMAN, reason_code="handoff_confirmed",
                )
        return None

    @staticmethod
    def rule_route(text: str, slots: dict[str, str]) -> RouteDecision | None:
        normalized = text.lower()
        if any(w in text for w in HUMAN_HANDOFF_KEYWORDS):
            return RouteDecision(Intent.HUMAN_HANDOFF, "human_handoff", slots, next_step=NextStep.TRANSFER_TO_HUMAN, reason_code="human_handoff_keyword")
        if any(w in text for w in OFFTOPIC_KEYWORDS):
            return RouteDecision(Intent.UNKNOWN, "offtopic", slots, next_step=NextStep.COLLECT_CLARIFICATION, reason_code="offtopic_keyword")
        if any(w in normalized for w in COMPLAINT_KEYWORDS):
            return RouteDecision(Intent.COMPLAINT, "complaint", slots, next_step=NextStep.TRANSFER_TO_HUMAN, reason_code="complaint_keyword")
        if any(w in normalized for w in REFUND_KEYWORDS):
            if any(w in text for w in POLICY_QUESTION_HINTS) and "订单" not in text:
                return RouteDecision(
                    Intent.KNOWLEDGE_QUERY, "knowledge_query", slots,
                    next_step=NextStep.RETRIEVE_KNOWLEDGE, reason_code="refund_policy_keyword",
                )
            missing = [] if slots.get("order_id") else ["order_id"]
            return RouteDecision(
                Intent.AFTER_SALES, "refund_only", slots, missing_slots=missing,
                next_step=NextStep.COLLECT_SLOTS if missing else NextStep.PREPARE_AFTER_SALES,
                reason_code="refund_keyword",
            )
        if any(w in normalized for w in LOGISTICS_KEYWORDS):
            missing = [] if slots.get("order_id") else ["order_id"]
            return RouteDecision(
                Intent.LOGISTICS_SERVICE, "logistics_query", slots, missing_slots=missing,
                next_step=NextStep.COLLECT_SLOTS if missing else NextStep.CALL_TOOL,
                reason_code="logistics_keyword",
            )
        if any(w in normalized for w in INVENTORY_KEYWORDS):
            missing = [] if slots.get("sku_id") else ["sku_id"]
            return RouteDecision(
                Intent.INVENTORY_QUERY, "inventory_query", slots, missing_slots=missing,
                next_step=NextStep.COLLECT_SLOTS if missing else NextStep.CALL_TOOL,
                reason_code="inventory_keyword",
            )
        if any(w in normalized for w in ("订单", "ord-")):
            missing = [] if slots.get("order_id") else ["order_id"]
            return RouteDecision(
                Intent.ORDER_SERVICE, "order_query", slots, missing_slots=missing,
                next_step=NextStep.COLLECT_SLOTS if missing else NextStep.CALL_TOOL,
                reason_code="order_keyword",
            )
        if any(w in normalized for w in KNOWLEDGE_KEYWORDS):
            return RouteDecision(Intent.KNOWLEDGE_QUERY, "knowledge_query", slots, next_step=NextStep.RETRIEVE_KNOWLEDGE, reason_code="knowledge_keyword")
        if any(g in normalized for g in GREETINGS) or len(text.strip()) <= 4:
            return RouteDecision(Intent.CHITCHAT, "casual_chat", slots, next_step=NextStep.DIRECT_REPLY, reason_code="chitchat")
        return None

    @staticmethod
    async def llm_route(text: str, slots: dict[str, str]) -> RouteDecision:
        if settings.llm_provider.lower() == "mock":
            return RouteDecision(Intent.UNKNOWN, "offtopic", slots, next_step=NextStep.COLLECT_CLARIFICATION, reason_code="offline_fallback")
        try:
            client = _llm_client()
            prompt = (
                '你是电商客服意图分类器，只输出JSON。格式：'
                '{"intent":"chitchat|knowledge_query|order_service|logistics_service|inventory_query|after_sales|complaint|human_handoff|unknown",'
                '"action":"string","slots":{"order_id":"optional","sku_id":"optional"},'
                '"next_step":"direct_reply|retrieve_knowledge|call_tool|collect_slots|prepare_after_sales|transfer_to_human"}\n'
                f"用户消息：{text}"
            )
            response = await asyncio.to_thread(client.invoke, prompt)
            content = str(response.content).strip()
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if not match:
                return RouteDecision(Intent.UNKNOWN, "unknown", slots, next_step=NextStep.TRANSFER_TO_HUMAN, reason_code="llm_parse_fail")
            data = json.loads(match.group(0))
            intent_str = str(data.get("intent", "unknown")).lower()
            intent = Intent(intent_str) if intent_str in [i.value for i in Intent] else Intent.UNKNOWN
            model_slots = data.get("slots") if isinstance(data.get("slots"), dict) else {}
            merged_slots = {k: v for k, v in {**slots, **model_slots}.items() if isinstance(v, str) and v.strip()}
            step_str = str(data.get("next_step", "direct_reply")).lower()
            step = NextStep(step_str) if step_str in [s.value for s in NextStep] else NextStep.DIRECT_REPLY
            return RouteDecision(intent, data.get("action", "unknown"), merged_slots, next_step=step, reason_code="llm_route")
        except Exception:
            return RouteDecision(Intent.CHITCHAT, "temporarily_unavailable", slots, next_step=NextStep.DIRECT_REPLY, reason_code="llm_route_fallback")

    async def route(self, text: str, state: dict[str, str] | None = None) -> RouteDecision:
        from .memory import expand_query, is_followup, is_recall

        slots = self.extract_slots(text)
        state = state or {"phase": "idle"}
        if decision := self.from_state(text, state, slots):
            return decision
        if is_recall(text) and (
            state.get("last_category") or state.get("last_order_id") or state.get("last_product_title")
        ):
            return RouteDecision(
                Intent.CHITCHAT, "recall_memory", slots,
                next_step=NextStep.DIRECT_REPLY, reason_code="memory_recall",
            )
        resolved = expand_query(text, state)
        if is_followup(text) and state.get("last_order_id") and not slots.get("order_id"):
            if any(word in text for word in ("订单", "物流", "快递", "到哪", "发货", "状态", "怎么样")):
                slots["order_id"] = str(state.get("last_order_id") or "")
        if decision := self.rule_route(resolved, slots):
            if (
                "order_id" in (decision.missing_slots or [])
                and state.get("last_order_id")
                and is_followup(text)
            ):
                decision.slots["order_id"] = str(state.get("last_order_id") or "")
                decision.missing_slots = [slot for slot in decision.missing_slots if slot != "order_id"]
                if decision.intent in (Intent.ORDER_SERVICE, Intent.LOGISTICS_SERVICE):
                    decision.next_step = NextStep.CALL_TOOL
            return decision
        last_intent = str(state.get("last_intent") or "")
        if is_followup(text) and last_intent in ("product", "unknown") and state.get("last_category"):
            return RouteDecision(
                Intent.KNOWLEDGE_QUERY, "knowledge_query", slots,
                next_step=NextStep.RETRIEVE_KNOWLEDGE, reason_code="memory_followup",
            )
        if is_followup(text) and last_intent in ("order", "shipment", "refund") and state.get("last_order_id"):
            slots["order_id"] = str(state.get("last_order_id") or "")
            return RouteDecision(
                Intent.ORDER_SERVICE, "order_query", slots,
                next_step=NextStep.CALL_TOOL, reason_code="memory_followup",
            )
        return await self.llm_route(resolved, slots)


intent_router = IntentRouter()
