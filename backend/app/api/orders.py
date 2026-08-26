# 订单查询相关 API 路由（只读，数据来自抖店 Provider）
from fastapi import APIRouter, Depends, HTTPException

from ..core.doudian_provider import DoudianProviderError, OrderNotFoundError, get_provider
from ..models import User
from ..schemas import OrderOut
from .deps import get_current_user


router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(order_id: str, user: User = Depends(get_current_user)) -> OrderOut:
    # 订单详情只读接口，404/502 对应 Provider 的错误语义
    try:
        data = await get_provider().get_order(order_id)
    except OrderNotFoundError:
        raise HTTPException(status_code=404, detail="订单不存在") from None
    except DoudianProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return OrderOut(**data)


@router.get("", response_model=list[OrderOut])
async def list_orders(
    customer: str | None = None,
    user: User = Depends(get_current_user),
) -> list[OrderOut]:
    # 按客户姓名或手机号模糊查询订单
    data = await get_provider().list_orders(customer)
    return [OrderOut(**item) for item in data]
