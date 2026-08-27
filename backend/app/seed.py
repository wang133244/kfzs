# 种子数据初始化：建表并写入默认 admin 账号与示例订单/库存数据
from decimal import Decimal

from sqlalchemy import delete, select, text

from .config import settings
from .data.showcase import PRODUCTS
from .db import async_session_factory, engine, ensure_mysql_database, retry_mysql_connect
from .models import Base, ChatSession, ConversationSummary, Message, Order, ProductInventory, User, WorkflowState
from .security import hash_password


# 种子订单：金额用 Decimal 保证与数据库 Numeric 类型一致
ORDERS = [
    {
        "order_id": "1001",
        "customer": "张三",
        "product": "太阳能柱头灯",
        "amount": Decimal("350.00"),
        "status": "paid",
    },
    {
        "order_id": "1002",
        "customer": "李四",
        "product": "中式户外壁灯",
        "amount": Decimal("105.00"),
        "status": "refunding",
    },
    {
        "order_id": "1003",
        "customer": "王五",
        "product": "LED 户外壁灯",
        "amount": Decimal("100.00"),
        "status": "shipped",
    },
    {
        "order_id": "1004",
        "customer": "赵六",
        "product": "太阳能庭院灯",
        "amount": Decimal("180.00"),
        "status": "unpaid",
    },
    {
        "order_id": "1005",
        "customer": "张三",
        "product": "新中式太阳能柱头灯",
        "amount": Decimal("120.00"),
        "status": "paid",
    },
]

# 种子库存：由橱窗商品的 SKU 统一生成，Celery 定时任务会按 threshold 生成库存预警
INVENTORY_ITEMS = [
    {
        "sku_id": sku["sku_id"],
        "sku_name": product["title"],
        "stock": sku["stock"],
        "threshold": sku["threshold"],
    }
    for product in PRODUCTS
    for sku in product["skus"]
]


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # 幂等迁移：SQLite 的 create_all 不会为已有表补充新列，需手动 ALTER
        if settings.is_sqlite:
            await _ensure_column(conn, "products", "source_url", "source_url TEXT NOT NULL DEFAULT ''")
            await _ensure_column(
                conn, "messages", "product_cards_json", "product_cards_json TEXT NOT NULL DEFAULT '[]'"
            )
            await _ensure_column(conn, "users", "openid", "openid VARCHAR(64)")
            await _ensure_column(conn, "users", "avatar_url", "avatar_url VARCHAR(512) NOT NULL DEFAULT ''")
            await _ensure_column(
                conn,
                "users",
                "wallet_balance",
                "wallet_balance NUMERIC(12, 2) NOT NULL DEFAULT 2000",
            )
            await _ensure_column(conn, "orders", "user_id", "user_id INTEGER")
            await _ensure_column(conn, "users", "cart_json", "cart_json TEXT NOT NULL DEFAULT '[]'")


async def _ensure_column(conn, table: str, column: str, ddl: str) -> None:
    rows = (await conn.execute(text(f"PRAGMA table_info({table})"))).fetchall()
    existing = {row[1] for row in rows}
    if existing and column not in existing:
        await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))


async def _ensure_account(session, username: str, password: str, role: str) -> None:
    # 每次启动按配置同步测试账号密码，避免云上旧库对不上 README 账号
    hashed = hash_password(password)
    row = await session.scalar(select(User).where(User.username == username))
    if row is None:
        session.add(
            User(
                username=username,
                password_hash=hashed,
                role=role,
                avatar_url="",
            )
        )
        return
    row.password_hash = hashed
    row.role = role


async def seed_all() -> None:
    # 幂等初始化：用户/订单已存在时跳过，可重复执行
    await create_tables()
    async with async_session_factory() as session:
        await _ensure_account(session, settings.admin_username, settings.admin_password, "admin")
        await _ensure_account(session, settings.staff_username, settings.staff_password, "staff")
        await _ensure_account(session, settings.customer_username, settings.customer_password, "customer")

        for order_data in ORDERS:
            existing = await session.scalar(
                select(Order).where(Order.order_id == order_data["order_id"])
            )
            if existing is None:
                session.add(Order(**order_data))

        # 初始化库存表：从 showcase 种子商品的 SKU 生成，已存在则跳过
        for product in PRODUCTS:
            for sku in product["skus"]:
                existing_inv = await session.scalar(
                    select(ProductInventory).where(ProductInventory.sku_id == sku["sku_id"])
                )
                if existing_inv is None:
                    session.add(
                        ProductInventory(
                            sku_id=sku["sku_id"],
                            product_id=product["product_id"],
                            sku_name=product["title"],
                            stock=sku["stock"],
                            threshold=sku.get("threshold", 10),
                        )
                    )

        # 统一提交本次写入，保证事务原子性
        await session.commit()


async def wipe_chat_history() -> None:
    # 一次性清空聊天会话与消息，不影响订单、商品和账号
    async with async_session_factory() as session:
        await session.execute(delete(Message))
        await session.execute(delete(ConversationSummary))
        await session.execute(delete(WorkflowState))
        await session.execute(delete(ChatSession))
        await session.commit()


# 初始化总入口：建表并写入种子数据（供应用启动与独立脚本调用）
async def init_db() -> None:
    await ensure_mysql_database()
    await retry_mysql_connect(seed_all)
    # 商品入库与内存同步：补齐种子灯具，并清掉旧占位商品
    from .core.product_service import seed_and_sync_products
    await seed_and_sync_products()
