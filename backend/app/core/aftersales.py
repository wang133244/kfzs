import hashlib
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from ..db import async_session_factory
from ..models import AfterSalesPreview as PreviewModel
from .doudian_provider import get_provider


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AfterSalesService:
    """After-sales preview→confirm flow with idempotency keys."""

    async def create_preview(
        self,
        user_id: str,
        session_id: str,
        order_id: str,
        action: str,
        reason: str,
    ) -> dict | None:
        # Verify the order exists before creating a preview
        order = await get_provider().get_order(order_id)
        if not order:
            return None

        amount = float(order.get("amount", 0))
        expires_at = (_utcnow() + timedelta(minutes=15)).isoformat()

        async with async_session_factory() as db:
            preview = PreviewModel(
                user_id=user_id,
                session_id=session_id,
                order_id=order_id,
                action=action,
                reason=reason,
                amount=amount,
                status="pending",
            )
            db.add(preview)
            await db.commit()
            await db.refresh(preview)
            return {
                "preview_id": preview.id,
                "order_id": order_id,
                "action": action,
                "reason": reason,
                "amount": amount,
                "expires_at": expires_at,
                "requires_confirmation": True,
            }

    async def confirm_preview(
        self,
        user_id: str,
        preview_id: str,
        idempotency_key: str,
    ) -> dict:
        key_hash = hashlib.sha256(idempotency_key.encode()).hexdigest()

        async with async_session_factory() as db:
            preview = await db.get(PreviewModel, preview_id)
            if not preview or preview.user_id != user_id:
                raise ValueError("售后预览不存在或不属于当前用户")

            # Idempotency: same key + already submitted = return same result
            if preview.status == "submitted":
                if preview.idempotency_key_hash == key_hash and preview.after_sales_id:
                    return {"after_sales_id": preview.after_sales_id, "status": "accepted", "idempotent": True}
                raise ValueError("该售后预览已经提交过了")

            # Check expiry
            if preview.status == "expired" or (
                _utcnow() - preview.created_at.replace(tzinfo=None) > timedelta(minutes=15)
            ):
                preview.status = "expired"
                await db.commit()
                raise ValueError("售后预览已过期，请重新发起申请")

            # Execute the after-sales via provider (or create human task)
            from .tools import create_human_task
            task_id = await create_human_task("refund", {
                "return_order_no": preview.order_id,
                "action": preview.action,
                "reason": preview.reason,
            })

            after_sales_id = f"AS-{preview.order_id[-4:]}"
            preview.status = "submitted"
            preview.idempotency_key_hash = key_hash
            preview.after_sales_id = after_sales_id
            await db.commit()

            return {
                "after_sales_id": after_sales_id,
                "status": "accepted",
                "task_id": task_id,
                "idempotent": False,
            }

    async def list_previews(self, user_id: str) -> list[dict]:
        async with async_session_factory() as db:
            rows = await db.scalars(
                select(PreviewModel)
                .where(PreviewModel.user_id == user_id, PreviewModel.status != "deleted")
                .order_by(PreviewModel.created_at.desc())
                .limit(20)
            )
            return [
                {
                    "preview_id": r.id,
                    "order_id": r.order_id,
                    "action": r.action,
                    "amount": float(r.amount),
                    "status": r.status,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in list(rows)
            ]


aftersales_service = AfterSalesService()
