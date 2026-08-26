# 购物车下单订单号：按当前时间生成，例如 2024.12.3.8.23.12
from datetime import datetime, timedelta, timezone

CHINA_TZ = timezone(timedelta(hours=8))


def now_china() -> datetime:
    return datetime.now(CHINA_TZ)


def build_order_id(now: datetime | None = None, seq: int = 0) -> str:
    stamp = now or now_china()
    base = f"{stamp.year}.{stamp.month}.{stamp.day}.{stamp.hour}.{stamp.minute}.{stamp.second}"
    if seq <= 0:
        return base
    return f"{base}.{seq}"
