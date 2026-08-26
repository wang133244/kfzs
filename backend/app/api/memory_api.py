from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..core.memory import memory_service
from .deps import get_current_user

router = APIRouter(tags=["memory"])


class ConsentRequest(BaseModel):
    enabled: bool


@router.put("/memory/consent")
async def set_consent(req: ConsentRequest, user=Depends(get_current_user)) -> dict:
    await memory_service.set_consent(str(user.id), req.enabled)
    return {"enabled": req.enabled}


@router.get("/memory/consent")
async def get_consent(user=Depends(get_current_user)) -> dict:
    return {"enabled": await memory_service.has_consent(str(user.id))}


@router.get("/memory/list")
async def list_memories(user=Depends(get_current_user)) -> list[dict]:
    return await memory_service.list_memories(str(user.id))


@router.delete("/memory/{memory_id}")
async def delete_memory(memory_id: int, user=Depends(get_current_user)) -> dict:
    if not await memory_service.forget_memory(str(user.id), memory_id):
        raise HTTPException(404, "记忆不存在")
    return {"deleted": True}


@router.delete("/memory")
async def delete_all_memories(user=Depends(get_current_user)) -> dict:
    await memory_service.set_consent(str(user.id), False)
    return {"deleted": True, "enabled": False}
