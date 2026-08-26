import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import async_session_factory
from ..models import ConversationSummary, MemoryConsent, MemoryRecord, Message, WorkflowState

SHORT_TERM_LIMIT = 12
SUMMARY_THRESHOLD = 24

FOLLOWUP_HINTS = (
    "多少钱", "价格", "售价", "防水", "那个", "这个", "这款", "那款", "刚才",
    "上面", "还有", "再来", "再推荐", "换一个", "别的", "怎么样", "参数", "规格",
    "包邮", "能亮", "怎么装", "安装", "充电", "保修", "到哪", "状态", "呢",
)
RECALL_HINTS = ("记得", "刚才问", "我刚才", "上次问", "还记得")
CATEGORY_HINTS = ("户外壁灯", "柱头灯", "庭院灯", "壁灯", "太阳能")
_SKIP_FOLLOWUP = (
    "你好", "您好", "谢谢", "转人工", "天气", "股票", "不用", "不需要", "算了",
)


def is_recall(text: str) -> bool:
    return any(hint in (text or "") for hint in RECALL_HINTS)


def is_followup(text: str) -> bool:
    raw = (text or "").strip()
    if not raw or any(skip in raw for skip in _SKIP_FOLLOWUP):
        return False
    if is_recall(raw):
        return True
    if extract_category(raw) and not any(
        hint in raw for hint in ("那个", "这个", "刚才", "这款", "那款", "还有", "再来", "再推荐", "换一个")
    ):
        return False
    if any(hint in raw for hint in FOLLOWUP_HINTS):
        return True
    if len(raw) <= 6 and not any(hint in raw for hint in CATEGORY_HINTS) and "订单" not in raw:
        return True
    return False


def extract_category(text: str) -> str:
    for hint in CATEGORY_HINTS:
        if hint in (text or ""):
            return hint
    return ""


def expand_query(text: str, focus: dict | None) -> str:
    raw = (text or "").strip()
    focus = focus or {}
    if not raw or not is_followup(raw):
        return raw
    last_intent = str(focus.get("last_intent") or "")
    if last_intent in ("order", "shipment", "refund") and focus.get("last_order_id"):
        oid = str(focus.get("last_order_id") or "")
        if oid and oid not in raw:
            return f"订单 {oid} {raw}"
    topic = str(
        focus.get("last_product_title")
        or focus.get("last_category")
        or focus.get("last_product_query")
        or ""
    ).strip()
    if topic and topic not in raw:
        return f"{topic} {raw}"
    return raw


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class MemoryService:
    """Three-layer session memory: short-term, summary, and long-term, plus workflow state."""

    async def get_recent_messages(self, session_id: str, limit: int = SHORT_TERM_LIMIT) -> list[dict]:
        async with async_session_factory() as db:
            rows = await db.scalars(
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(desc(Message.id))
                .limit(limit)
            )
            return [{"role": r.role, "content": r.content} for r in reversed(list(rows))]

    async def get_summary(self, session_id: str) -> str:
        async with async_session_factory() as db:
            row = await db.scalar(
                select(ConversationSummary).where(ConversationSummary.session_id == session_id)
            )
            return row.summary if row else ""

    async def _refresh_summary(self, db: AsyncSession, session_id: str, user_id: str) -> None:
        rows = await db.scalars(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(desc(Message.id))
            .limit(200)
        )
        messages = list(reversed(list(rows)))
        if len(messages) <= SUMMARY_THRESHOLD:
            return
        older = messages[:-SUMMARY_THRESHOLD]
        lines: list[str] = []
        for item in older[-32:]:
            content = re.sub(r"\s+", " ", item.content).strip()
            if content:
                prefix = "用户" if item.role == "user" else "客服"
                lines.append(f"{prefix}：{content[:180]}")
        summary = "；".join(lines)[-4000:]
        existing = await db.scalar(
            select(ConversationSummary).where(ConversationSummary.session_id == session_id)
        )
        if existing:
            existing.summary = summary
            existing.message_count = len(older)
        else:
            db.add(ConversationSummary(
                session_id=session_id, user_id=user_id, summary=summary, message_count=len(older)
            ))

    async def append_message(self, session_id: str, user_id: str, role: str, content: str) -> None:
        async with async_session_factory() as db:
            db.add(Message(session_id=session_id, role=role, content=content))
            await db.commit()
            if role == "assistant":
                await self._refresh_summary(db, session_id, user_id)
                await db.commit()

    async def has_consent(self, user_id: str) -> bool:
        async with async_session_factory() as db:
            row = await db.scalar(select(MemoryConsent).where(MemoryConsent.user_id == user_id))
            return bool(row and row.enabled)

    async def set_consent(self, user_id: str, enabled: bool) -> None:
        async with async_session_factory() as db:
            row = await db.scalar(select(MemoryConsent).where(MemoryConsent.user_id == user_id))
            if row:
                row.enabled = enabled
            else:
                db.add(MemoryConsent(user_id=user_id, enabled=enabled))
            if not enabled:
                await db.execute(
                    select(MemoryRecord).where(MemoryRecord.user_id == user_id)
                )
                records = await db.scalars(
                    select(MemoryRecord).where(MemoryRecord.user_id == user_id)
                )
                for record in list(records):
                    await db.delete(record)
            await db.commit()

    async def list_memories(self, user_id: str) -> list[dict]:
        async with async_session_factory() as db:
            rows = await db.scalars(
                select(MemoryRecord)
                .where(MemoryRecord.user_id == user_id)
                .order_by(desc(MemoryRecord.id))
            )
            return [
                {
                    "id": r.id,
                    "kind": r.kind,
                    "content": r.content,
                    "source": r.source,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in list(rows)
            ]

    async def forget_memory(self, user_id: str, memory_id: int) -> bool:
        async with async_session_factory() as db:
            row = await db.scalar(
                select(MemoryRecord).where(
                    MemoryRecord.id == memory_id, MemoryRecord.user_id == user_id
                )
            )
            if not row:
                return False
            await db.delete(row)
            await db.commit()
            return True

    async def refresh_summary(self, session_id: str, user_id: str) -> None:
        async with async_session_factory() as db:
            await self._refresh_summary(db, session_id, user_id)
            await db.commit()

    async def capture_explicit_memory(self, user_id: str, text: str) -> dict | None:
        match = re.search(r"(?:请)?记住(?:我)?(.+)", text.strip())
        if not match:
            return None
        content = match.group(1).strip("，。！! ")
        if not content or self._contains_sensitive(content):
            return None
        if not await self.has_consent(user_id):
            await self.set_consent(user_id, True)
        async with async_session_factory() as db:
            record = MemoryRecord(
                user_id=user_id, kind="semantic", content=content, source="user_explicit"
            )
            db.add(record)
            await db.commit()
            await db.refresh(record)
            return {
                "id": record.id,
                "kind": record.kind,
                "content": record.content,
                "source": record.source,
            }

    @staticmethod
    def _contains_sensitive(content: str) -> bool:
        patterns = [r"1[3-9]\d{9}", r"\d{15,18}[0-9Xx]", r"(?:地址|身份证|银行卡|密码|验证码)"]
        return any(re.search(p, content) for p in patterns)

    async def search_long_term(self, user_id: str, query: str, limit: int = 3) -> list[dict]:
        if not await self.has_consent(user_id):
            return []
        async with async_session_factory() as db:
            rows = await db.scalars(
                select(MemoryRecord)
                .where(MemoryRecord.user_id == user_id)
                .order_by(desc(MemoryRecord.id))
                .limit(50)
            )
            scored = []
            for r in list(rows):
                score = sum(1 for term in query if term in r.content)
                if score > 0:
                    scored.append((score, {"id": r.id, "content": r.content, "kind": r.kind}))
            return [item for _, item in sorted(scored, key=lambda x: x[0], reverse=True)[:limit]]

    async def save_workflow_state(self, session_id: str, user_id: str, phase: str, **extra: str) -> None:
        import json
        async with async_session_factory() as db:
            row = await db.scalar(
                select(WorkflowState).where(WorkflowState.session_id == session_id)
            )
            state = json.loads(row.state_json) if row and row.state_json else {}
            state.update(extra)
            if row:
                row.phase = phase
                row.state_json = json.dumps(state, ensure_ascii=False)
            else:
                db.add(WorkflowState(
                    session_id=session_id, user_id=user_id, phase=phase,
                    state_json=json.dumps(state, ensure_ascii=False),
                ))
            await db.commit()

    async def load_workflow_state(self, session_id: str) -> dict:
        import json
        async with async_session_factory() as db:
            row = await db.scalar(
                select(WorkflowState).where(WorkflowState.session_id == session_id)
            )
            if not row:
                return {"phase": "idle"}
            return {"phase": row.phase, **json.loads(row.state_json or "{}")}

    async def remember_interest(self, user_id: str, category: str) -> None:
        category = (category or "").strip()
        if not user_id or not category:
            return
        async with async_session_factory() as db:
            row = await db.scalar(
                select(MemoryRecord).where(
                    MemoryRecord.user_id == user_id,
                    MemoryRecord.kind == "preference",
                    MemoryRecord.source == "dialog",
                )
            )
            if row:
                row.content = category
            else:
                db.add(MemoryRecord(
                    user_id=user_id,
                    kind="preference",
                    content=category,
                    source="dialog",
                ))
            await db.commit()

    async def latest_interest(self, user_id: str) -> str:
        if not user_id:
            return ""
        async with async_session_factory() as db:
            row = await db.scalar(
                select(MemoryRecord)
                .where(
                    MemoryRecord.user_id == user_id,
                    MemoryRecord.kind == "preference",
                )
                .order_by(desc(MemoryRecord.id))
            )
            return (row.content or "") if row else ""

    async def save_dialog_focus(self, session_id: str, user_id: str, **focus: str) -> None:
        if not session_id:
            return
        current = await self.load_workflow_state(session_id)
        phase = str(current.get("phase") or "idle")
        extra = {key: str(value) for key, value in current.items() if key != "phase" and value is not None}
        extra.update({key: str(value) for key, value in focus.items() if value is not None and str(value)})
        await self.save_workflow_state(session_id, user_id, phase, **extra)

    async def clear_workflow_state(self, session_id: str) -> None:
        import json
        async with async_session_factory() as db:
            row = await db.scalar(
                select(WorkflowState).where(WorkflowState.session_id == session_id)
            )
            if not row:
                return
            data = json.loads(row.state_json or "{}")
            kept = {key: value for key, value in data.items() if str(key).startswith("last_")}
            row.phase = "idle"
            row.state_json = json.dumps(kept, ensure_ascii=False)
            await db.commit()

    async def build_context(self, session_id: str, user_id: str, query: str) -> dict:
        """Assemble all three memory layers plus workflow state for the agent."""
        workflow_state = await self.load_workflow_state(session_id)
        if not workflow_state.get("last_category"):
            interest = await self.latest_interest(user_id)
            if interest:
                workflow_state["last_category"] = interest
        return {
            "recent_messages": await self.get_recent_messages(session_id),
            "summary": await self.get_summary(session_id),
            "long_term": await self.search_long_term(user_id, query),
            "workflow_state": workflow_state,
        }


memory_service = MemoryService()
