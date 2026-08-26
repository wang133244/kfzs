# Celery 应用与定时调度配置：注册订单同步/库存预警等任务模块，并定义 beat 周期计划
from celery import Celery

from ..config import settings


# 创建 Celery 应用：broker 与结果后端均为 Redis，同时注册两个任务模块
celery_app = Celery(
    "doudian_agent",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.shipments", "app.tasks.inventory"],
)

# 统一时区为上海，并启用 beat 定时调度（具体任务与周期见下）
celery_app.conf.update(
    timezone="Asia/Shanghai",
    # 定时调度：订单同步 5 分钟一次，库存预警 15 分钟一次
    beat_schedule={
        "sync-orders-every-5-min": {
            "task": "tasks.sync_orders",
            "schedule": 300.0,
        },
        "check-inventory-alert-every-15-min": {
            "task": "tasks.check_inventory_alert",
            "schedule": 900.0,
        },
    },
)
