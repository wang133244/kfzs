import asyncio
import logging
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import admin, aftersales, auth, chat, doudian_sim, evaluation, knowledge, memory_api, orders, sessions, shop
from .api import human_chat, product_admin
from .config import settings
from .seed import init_db

logger = logging.getLogger(__name__)


async def _warm_rag() -> None:
    # 知识库重建放到后台，避免云托管健康检查在端口尚未监听时判定失败
    try:
        from .rag.store import get_collection
        from .core.ingestion import ingestion_service

        get_collection(rebuild=True)
        for doc in await ingestion_service.list_documents():
            if doc["status"] == "ready":
                await ingestion_service.reindex_document(doc["document_id"])
    except Exception:
        logger.exception("RAG warmup failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    warmup = asyncio.create_task(_warm_rag())
    yield
    warmup.cancel()
    try:
        await warmup
    except (asyncio.CancelledError, Exception):
        logger.debug("RAG warmup stopped", exc_info=True)


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(sessions.router, prefix="/api/v1")
app.include_router(orders.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(human_chat.router, prefix="/api/v1")
app.include_router(product_admin.router, prefix="/api/v1")
app.include_router(shop.router, prefix="/api/v1")
app.include_router(doudian_sim.router, prefix="/api/v1")
app.include_router(knowledge.router, prefix="/api/v1")
app.include_router(evaluation.router, prefix="/api/v1")
app.include_router(memory_api.router, prefix="/api/v1")
app.include_router(aftersales.router, prefix="/api/v1")

_UPLOAD_ROOT = Path(__file__).resolve().parents[1] / "uploads"
_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
(_UPLOAD_ROOT / "avatars").mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=_UPLOAD_ROOT), name="uploads")


@app.get("/")
@app.get("/api/v1/healthz")
async def healthz() -> dict:
    # 云托管默认探测根路径；/api/v1/healthz 供业务侧检查
    return {"status": "ok"}



@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    detail = errors[0].get("msg", "请求参数错误") if errors else "请求参数错误"
    return JSONResponse(status_code=422, content={"detail": detail})
