# 数据库基础设施：创建异步引擎与会话工厂，并提供 FastAPI 请求级数据库会话依赖
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool

from .config import settings


class Base(DeclarativeBase):
    pass


def _ensure_sqlite_parent(database_url: str) -> None:
    # SQLite 文件路径的父目录不存在时自动创建，避免启动失败
    if not database_url.startswith("sqlite+aiosqlite:///"):
        return
    db_path = database_url.removeprefix("sqlite+aiosqlite:///")
    if not db_path or db_path == ":memory:":
        return
    parent = Path(db_path).parent
    if str(parent) not in ("", "."):
        parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_parent(settings.database_url)

engine_kwargs: dict = {"echo": False, "future": True}
if settings.database_url == "sqlite+aiosqlite:///:memory:":
    engine_kwargs["poolclass"] = StaticPool
    engine_kwargs["connect_args"] = {"check_same_thread": False}

# 全局异步引擎，启动时创建一次，供建表与会话工厂复用
engine = create_async_engine(settings.database_url, **engine_kwargs)
# 所有异步数据库操作统一通过该 session factory 创建会话
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db():
    # FastAPI 依赖：每个请求使用独立数据库会话
    async with async_session_factory() as session:
        yield session


# Make `python -m app.db.init_db` resolve while keeping app/db.py as the
# canonical module for engine/session helpers.
__path__ = [str(Path(__file__).resolve().parent / "db")]
