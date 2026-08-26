from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..core.aftersales import aftersales_service
from .deps import get_current_user

router = APIRouter(tags=["aftersales"])


class PreviewRequest(BaseModel):
    session_id: str = ""
    order_id: str
    action: str = "refund_only"
    reason: str = Field(min_length=2, max_length=500)


class ConfirmRequest(BaseModel):
    preview_id: str
    idempotency_key: str = Field(min_length=8, max_length=128)


@router.post("/aftersales/preview")
async def create_preview(req: PreviewRequest, user=Depends(get_current_user)) -> dict:
    try:
        result = await aftersales_service.create_preview(
            str(user.id), req.session_id, req.order_id, req.action, req.reason
        )
        if not result:
            raise HTTPException(400, "未找到该订单，无法生成售后预览")
        return result
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/aftersales/confirm")
async def confirm_preview(req: ConfirmRequest, user=Depends(get_current_user)) -> dict:
    try:
        return await aftersales_service.confirm_preview(str(user.id), req.preview_id, req.idempotency_key)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/aftersales/previews")
async def list_previews(user=Depends(get_current_user)) -> list[dict]:
    return await aftersales_service.list_previews(str(user.id))
