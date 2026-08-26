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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化数据库与 RAG 知识库，确保首次请求即可使用
    await init_db()
    from .rag.store import get_collection
    from .core.ingestion import ingestion_service

    # 每次启动重建内置知识库，保证 Markdown 更新后无需手动清理向量库
    get_collection(rebuild=True)
    # 重新索引已就绪的 PDF 文档到 RAG
    for doc in await ingestion_service.list_documents():
        if doc["status"] == "ready":
            await ingestion_service.reindex_document(doc["document_id"])
    yield


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


@app.get("/api/v1/healthz")
async def healthz() -> dict:
    # 健康检查
    return {"status": "ok"}



@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    detail = errors[0].get("msg", "请求参数错误") if errors else "请求参数错误"
    return JSONResponse(status_code=422, content={"detail": detail})
