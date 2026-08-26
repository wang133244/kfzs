from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile

from ..core.ingestion import ingestion_service
from .deps import get_current_staff

router = APIRouter(tags=["knowledge"])


@router.get("/knowledge/documents")
async def list_documents(user=Depends(get_current_staff)) -> list[dict]:
    return await ingestion_service.list_documents()


@router.get("/knowledge/documents/{document_id}")
async def get_document(document_id: str, user=Depends(get_current_staff)) -> dict:
    doc = await ingestion_service.get_document(document_id)
    if not doc:
        raise HTTPException(404, "文档不存在")
    return doc


@router.post("/knowledge/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(default=""),
    user=Depends(get_current_staff),
) -> dict:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "仅支持 PDF 文件")
    data = await file.read()
    if len(data) > 50 * 1024 * 1024:
        raise HTTPException(413, "文件不能超过 50MB")
    result = await ingestion_service.create_document(file.filename, data, title)
    if result["status"] == "pending":
        background_tasks.add_task(ingestion_service.process_document, result["document_id"])
    return result


@router.delete("/knowledge/documents/{document_id}")
async def delete_document(document_id: str, user=Depends(get_current_staff)) -> dict:
    if not await ingestion_service.delete_document(document_id):
        raise HTTPException(404, "文档不存在")
    return {"deleted": True}


@router.post("/knowledge/documents/{document_id}/reindex")
async def reindex_document(
    document_id: str,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_staff),
) -> dict:
    async def _reindex():
        await ingestion_service.reindex_document(document_id)
    background_tasks.add_task(_reindex)
    return {"status": "reindexing", "document_id": document_id}


@router.get("/knowledge/documents/{document_id}/chunks")
async def get_chunks(document_id: str, user=Depends(get_current_staff)) -> list[dict]:
    return ingestion_service.document_chunks(document_id)
