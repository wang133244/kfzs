# 抖店开放平台 Provider：封装订单/库存/物流/售后的 API 调用，支持 Mock 与真实两种模式
import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any

import httpx
from sqlalchemy import or_, select

from ..config import Settings, settings
from ..db import async_session_factory
from ..models import Order
from ..seed import INVENTORY_ITEMS

logger = logging.getLogger(__name__)


class DoudianProviderError(Exception):
    # Provider 统一异常基类，接口报错、数据缺失等均抛出该类型
    pass


class OrderNotFoundError(DoudianProviderError):
    # 订单不存在时抛出，便于上层区分"未找到"与其它错误
    pass


class TokenExpiredError(DoudianProviderError):
    # token 刷新失败（凭证彻底失效）时抛出，提示需要重新授权
    pass


def build_sign(app_secret: str, method: str, param_json: str, timestamp: str) -> str:
    # 抖店开放平台要求的 MD5 签名算法，前后拼接两次 app_secret
    raw = f"{app_secret}{method}{param_json}{timestamp}{app_secret}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


class BaseDoudianProvider(ABC):
    # Provider 抽象基类，Mock 与真实实现必须保持相同方法签名
    @abstractmethod
    async def get_order(self, order_id: str) -> dict:
        raise DoudianProviderError("BaseDoudianProvider 不能直接调用，请使用 Mock 或真实 Provider")

    @abstractmethod
    async def list_orders(self, customer: str | None = None) -> list[dict]:
        raise DoudianProviderError("BaseDoudianProvider 不能直接调用，请使用 Mock 或真实 Provider")

    @abstractmethod
    async def get_inventory(self, sku_id: str) -> int:
        raise DoudianProviderError("BaseDoudianProvider 不能直接调用，请使用 Mock 或真实 Provider")

    @abstractmethod
    async def create_shipment(
        self,
        order_id: str,
        company_code: str,
        logistics_code: str,
    ) -> dict:
        raise DoudianProviderError("BaseDoudianProvider 不能直接调用，请使用 Mock 或真实 Provider")

    @abstractmethod
    async def approve_refund(self, return_order_no: str) -> dict:
        raise DoudianProviderError("BaseDoudianProvider 不能直接调用，请使用 Mock 或真实 Provider")

    @abstractmethod
    async def reject_refund(self, return_order_no: str, reason: str) -> dict:
        raise DoudianProviderError("BaseDoudianProvider 不能直接调用，请使用 Mock 或真实 Provider")


# Mock 发货数据：为已发货订单补充模拟的物流公司与运单号
_SHIPPED_LOGISTICS = {
    "1003": {"company_code": "SF", "logistics_code": "SF1234567890"},
}


class MockDoudianProvider(BaseDoudianProvider):
    # 离线模式：订单读数据库种子数据，写操作只记录日志
    async def get_order(self, order_id: str) -> dict:
        # 按订单号读取数据库；已发货订单额外附加 Mock 物流信息
        async with async_session_factory() as session:
            order = await session.scalar(select(Order).where(Order.order_id == order_id))
        if order is None:
            raise OrderNotFoundError(f"订单 {order_id} 不存在")
        result = self._order_to_dict(order)
        logistics = _SHIPPED_LOGISTICS.get(order_id)
        if logistics and order.status == "shipped":
            result["company_code"] = logistics["company_code"]
            result["logistics_code"] = logistics["logistics_code"]
        return result

    async def list_orders(self, customer: str | None = None) -> list[dict]:
        # 按客户名模糊查询订单列表（未传客户则返回全部），按创建时间倒序
        stmt = select(Order).order_by(Order.created_at.desc())
        if customer:
            stmt = stmt.where(
                or_(
                    Order.customer == customer,
                    Order.customer.like(f"%{customer}%"),
                )
            )
        async with async_session_factory() as session:
            orders = (await session.scalars(stmt)).all()
        return [self._order_to_dict(order) for order in orders]

    async def get_inventory(self, sku_id: str) -> int:
        # 优先从数据库 ProductInventory 表读取库存（与下单扣减同一数据源），
        # 数据库无记录时回退到内存种子数据
        from ..models import ProductInventory
        async with async_session_factory() as session:
            inv = await session.scalar(
                select(ProductInventory).where(ProductInventory.sku_id == sku_id)
            )
        if inv is not None:
            return inv.stock
        # 回退到内存种子数据，兼容未初始化库存表的场景
        item = next((i for i in INVENTORY_ITEMS if i["sku_id"] == sku_id), None)
        if item is None:
            raise DoudianProviderError(f"SKU {sku_id} 不存在")
        return item["stock"]

    async def create_shipment(
        self,
        order_id: str,
        company_code: str,
        logistics_code: str,
    ) -> dict:
        # Mock 写操作：只记录日志并返回成功，不产生真实副作用
        logger.info("mock create_shipment order_id=%s company=%s code=%s", order_id, company_code, logistics_code)
        return {
            "status": "success",
            "order_id": order_id,
            "company_code": company_code,
            "logistics_code": logistics_code,
        }

    async def approve_refund(self, return_order_no: str) -> dict:
        # Mock 写操作：只记录日志并返回成功
        logger.info("mock approve_refund return_order_no=%s", return_order_no)
        return {"status": "success", "return_order_no": return_order_no}

    async def reject_refund(self, return_order_no: str, reason: str) -> dict:
        # Mock 写操作：只记录日志并返回成功
        logger.info("mock reject_refund return_order_no=%s reason=%s", return_order_no, reason)
        return {"status": "success", "return_order_no": return_order_no, "reason": reason}

    @staticmethod
    def _order_to_dict(order: Order) -> dict[str, Any]:
        # 将 Order ORM 对象序列化为对外返回的 dict
        return {
            "order_id": order.order_id,
            "customer": order.customer,
            "product": order.product,
            "amount": float(order.amount),
            "status": order.status,
            "created_at": order.created_at,
            "updated_at": order.updated_at,
        }


class DoudianOpenAPIProvider(BaseDoudianProvider):
    # 真实模式：调用抖店 openapi-fxg 接口，带签名与 token 刷新
    def __init__(self, s: Settings) -> None:
        # 读取凭证配置并创建带 15s 超时的 HTTP 客户端
        self.app_key = s.doudian_app_key
        self.app_secret = s.doudian_app_secret
        self.access_token = s.doudian_access_token
        self.refresh_token = s.doudian_refresh_token
        self.base_url = s.doudian_base_url
        self._client = httpx.AsyncClient(base_url=s.doudian_base_url, timeout=15.0)

    async def _request(self, method: str, params: dict, retry: bool = False) -> dict:
        # 组装公共参数并签名；token 失效时刷新后最多重试一次
        timestamp = str(int(time.time()))
        param_json = json.dumps(params, ensure_ascii=False, separators=(",", ":"))
        sign = build_sign(self.app_secret, method, param_json, timestamp)
        payload = {
            "method": method,
            "app_key": self.app_key,
            "access_token": self.access_token,
            "param_json": param_json,
            "timestamp": timestamp,
            "v": "2",
            "sign": sign,
            "sign_method": "md5",
        }
        response = await self._client.post("/router/rest", data=payload)
        response.raise_for_status()
        data = response.json()

        if self._is_token_invalid(data) and not retry:
            await self._refresh_token()
            return await self._request(method, params, retry=True)
        if data.get("err_no") not in (0, None):
            raise DoudianProviderError(
                f"抖店接口 {method} 调用失败: {data.get('err_msg') or data.get('message') or data}"
            )
        return data.get("data") or {}

    def _is_token_invalid(self, data: dict) -> bool:
        # 40010 等错误码或错误信息包含 token 时判定为凭证失效
        err_no = data.get("err_no")
        if err_no in (40010, 40002, 40011):
            return True
        message = str(data.get("err_msg") or data.get("message") or "")
        return "token" in message.lower() and ("invalid" in message.lower() or "失效" in message)

    async def _refresh_token(self) -> None:
        # 使用 refresh_token 换取新 token；失败时抛出明确错误
        params = {"refresh_token": self.refresh_token}
        param_json = json.dumps(params, ensure_ascii=False, separators=(",", ":"))
        method = "oauth2.refreshToken"
        timestamp = str(int(time.time()))
        sign = build_sign(self.app_secret, method, param_json, timestamp)
        payload = {
            "method": method,
            "app_key": self.app_key,
            "param_json": param_json,
            "timestamp": timestamp,
            "v": "2",
            "sign": sign,
            "sign_method": "md5",
        }
        response = await self._client.post("/router/rest", data=payload)
        response.raise_for_status()
        data = response.json()
        token_data = data.get("data") or {}
        new_token = token_data.get("access_token")
        new_refresh = token_data.get("refresh_token")
        if not new_token:
            raise TokenExpiredError("抖店 token 刷新失败，请重新授权")
        self.access_token = new_token
        if new_refresh:
            self.refresh_token = new_refresh

    async def get_order(self, order_id: str) -> dict:
        # 调用 order.orderDetail 查询订单详情，返回空视为订单不存在
        data = await self._request("order.orderDetail", {"order_id": order_id})
        if not data:
            raise OrderNotFoundError(f"订单 {order_id} 不存在")
        return data

    async def list_orders(self, customer: str | None = None) -> list[dict]:
        # 调用 order.searchList 查询订单列表，可按客户过滤
        params: dict = {}
        if customer:
            params["customer"] = customer
        data = await self._request("order.searchList", params)
        return data.get("order_list") or []

    async def get_inventory(self, sku_id: str) -> int:
        # 调用 sku.list 查询库存，库存字段缺失视为接口异常
        data = await self._request("sku.list", {"sku_id": sku_id})
        sku = data.get("sku") or {}
        stock = sku.get("stock_num")
        if stock is None:
            raise DoudianProviderError(f"SKU {sku_id} 库存信息缺失")
        return int(stock)

    async def create_shipment(
        self,
        order_id: str,
        company_code: str,
        logistics_code: str,
    ) -> dict:
        # 调用 order.logisticsAdd 创建发货单
        data = await self._request(
            "order.logisticsAdd",
            {
                "order_id": order_id,
                "company_code": company_code,
                "logistics_code": logistics_code,
            },
        )
        return {"status": "success", **data}

    async def approve_refund(self, return_order_no: str) -> dict:
        # 调用 afterSale.operate 同意退款
        data = await self._request(
            "afterSale.operate",
            {"return_order_no": return_order_no, "operate": "approve"},
        )
        return {"status": "success", "return_order_no": return_order_no, **data}

    async def reject_refund(self, return_order_no: str, reason: str) -> dict:
        # 调用 afterSale.operate 拒绝退款
        data = await self._request(
            "afterSale.operate",
            {
                "return_order_no": return_order_no,
                "operate": "reject",
                "reason": reason,
            },
        )
        return {"status": "success", "return_order_no": return_order_no, **data}


# Provider 单例缓存，首次访问时按配置创建
_provider: BaseDoudianProvider | None = None


def get_provider() -> BaseDoudianProvider:
    # 根据 DOUDIAN_PROVIDER 配置返回单例 Provider
    global _provider
    if _provider is None:
        if settings.doudian_provider.lower() == "real":
            _provider = DoudianOpenAPIProvider(settings)
        else:
            _provider = MockDoudianProvider()
    return _provider
