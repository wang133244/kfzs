import re

import pytest

from app.core.doudian_provider import (
    MockDoudianProvider,
    OrderNotFoundError,
    build_sign,
)


@pytest.mark.asyncio
async def test_mock_get_order_returns_order():
    provider = MockDoudianProvider()
    order = await provider.get_order("1001")
    assert order["order_id"] == "1001"
    assert order["customer"] == "张三"
    assert order["product"] == "太阳能柱头灯"


@pytest.mark.asyncio
async def test_mock_missing_order_raises_clear_error():
    provider = MockDoudianProvider()
    with pytest.raises(OrderNotFoundError, match="不存在"):
        await provider.get_order("99999")


def test_build_sign_returns_32_char_md5():
    sign = build_sign("secret", "order.orderDetail", "{}", "1700000000")
    assert len(sign) == 32
    assert re.fullmatch(r"[0-9a-f]{32}", sign) is not None
