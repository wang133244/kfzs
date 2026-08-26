# 库存预警定时任务：周期检查各 SKU 库存，低于阈值时写入未处理的库存预警
import asyncio

from sqlalchemy import select

from ..core.doudian_provider import DoudianProviderError, get_provider
from ..db import async_session_factory
from ..models import InventoryAlert
from ..seed import INVENTORY_ITEMS
from .celery_app import celery_app


# 库存检查核心逻辑（异步）：查询实时库存并生成低库存预警，供定时任务调用
async def _check_inventory() -> None:
    # 遍历种子 SKU，库存低于阈值且未处理时写入库存预警
    provider = get_provider()
    async with async_session_factory() as session:
        for item in INVENTORY_ITEMS:
            try:
                stock = await provider.get_inventory(item["sku_id"])
            except DoudianProviderError:
                # 单个 SKU 查询失败跳过，不影响其余 SKU 的检查
                continue
            # 库存充足时无需预警，跳过该 SKU
            if stock > item["threshold"]:
                continue
            # 幂等处理：同一 SKU 已有未处理预警则不再重复插入
            existing = await session.scalar(
                select(InventoryAlert).where(
                    InventoryAlert.sku_id == item["sku_id"],
                    InventoryAlert.handled.is_(False),
                )
            )
            if existing is None:
                session.add(
                    InventoryAlert(
                        sku_id=item["sku_id"],
                        sku_name=item["sku_name"],
                        current_stock=stock,
                        threshold=item["threshold"],
                        handled=False,
                    )
                )
        await session.commit()


# Celery 任务入口：在事件循环中执行库存检查，由 beat 定时触发
@celery_app.task(name="tasks.check_inventory_alert")
def check_inventory_alert() -> None:
    asyncio.run(_check_inventory())
