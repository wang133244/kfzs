# 数据库基础设施：创建异步引擎与会话工厂，并提供 FastAPI 请求级数据库会话依赖
import asyncio
import re
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool

from .config import settings

_MYSQL_IDENT = re.compile(r"^[A-Za-z0-9_]+$")


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


def _engine_kwargs(database_url: str) -> dict:
    kwargs: dict = {"echo": False, "future": True}
    if database_url == "sqlite+aiosqlite:///:memory:":
        kwargs["poolclass"] = StaticPool
        kwargs["connect_args"] = {"check_same_thread": False}
    elif database_url.startswith("mysql"):
        # 云托管 MySQL 会空闲暂停，连前探活并回收旧连接
        kwargs["pool_pre_ping"] = True
        kwargs["pool_recycle"] = 280
    return kwargs


_ensure_sqlite_parent(settings.resolved_database_url)

# 全局异步引擎，启动时创建一次，供建表与会话工厂复用
engine = create_async_engine(settings.resolved_database_url, **_engine_kwargs(settings.resolved_database_url))
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


async def retry_mysql_connect(operation, attempts: int = 10):
    # 云托管 MySQL 冷启动时会返回 CynosDB resuming，短暂重试即可
    last: Exception | None = None
    for i in range(attempts):
        try:
            return await operation()
        except Exception as exc:
            message = str(exc).lower()
            if "resuming" in message or "cynosdb" in message:
                last = exc
                await asyncio.sleep(min(2 * (i + 1), 15))
                continue
            raise
    if last is not None:
        raise last
    raise RuntimeError("MySQL 连接重试失败")


async def ensure_mysql_database() -> None:
    # 库不存在时自动创建，避免控制台只开通实例却没建 doudian
    url = settings.resolved_database_url
    if not url.startswith("mysql"):
        return
    parsed = make_url(url)
    db_name = parsed.database or "doudian"
    if not _MYSQL_IDENT.fullmatch(db_name):
        raise ValueError(f"非法数据库名: {db_name}")
    admin_engine = create_async_engine(
        parsed.set(database=None),
        **_engine_kwargs(url),
    )
    try:
        async def _create() -> None:
            async with admin_engine.begin() as conn:
                await conn.execute(
                    text(
                        f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                    )
                )

        await retry_mysql_connect(_create)
    finally:
        await admin_engine.dispose()


# Make `python -m app.db.init_db` resolve while keeping app/db.py as the
# canonical module for engine/session helpers.
__path__ = [str(Path(__file__).resolve().parent / "db")]
