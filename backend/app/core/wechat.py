# 微信小程序登录：用 wx.login 的 code 换 openid
import logging

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

JSCODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"


async def code_to_openid(code: str) -> str | None:
    # 配置了 AppSecret 时走真实微信接口；开发者工具未配密钥则返回 None，由调用方用 local_key 兜底
    code = (code or "").strip()
    if not code or not settings.wechat_appid or not settings.wechat_secret:
        return None
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                JSCODE2SESSION_URL,
                params={
                    "appid": settings.wechat_appid,
                    "secret": settings.wechat_secret,
                    "js_code": code,
                    "grant_type": "authorization_code",
                },
            )
            data = response.json()
    except Exception:
        logger.exception("wechat jscode2session failed")
        return None
    openid = data.get("openid")
    if not openid:
        logger.warning("wechat jscode2session error: %s", data)
        return None
    return str(openid)
