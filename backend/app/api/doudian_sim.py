# 模拟抖店开放平台网关 API：请求/响应结构与真实网关一致，便于无凭证演示
import json

from fastapi import APIRouter, Request
from fastapi import Depends

from ..core.doudian_sim import METHODS, handle_doudian_method
from ..models import User
from .deps import get_current_staff


router = APIRouter(prefix="/sim/doudian", tags=["sim-doudian"])


@router.get("/methods")
async def sim_methods(user: User = Depends(get_current_staff)) -> dict:
    # 网关能力说明：列出模拟支持的方法与调用方式
    return {
        "gateway": "POST /api/v1/sim/doudian/router/rest",
        "request_format": {"method": "product.search", "param_json": "{}"},
        "response_structure": {"err_no": 0, "err_msg": "success", "data": {}},
        "methods": METHODS,
    }


@router.post("/router/rest")
async def sim_router_rest(request: Request, user: User = Depends(get_current_staff)) -> dict:
    # 兼容 form-urlencoded（与真实网关一致）与 JSON 两种请求体
    content_type = request.headers.get("content-type", "").lower()
    if content_type.startswith("application/json"):
        body = await request.json()
        method = str(body.get("method") or "")
        raw_params = body.get("param_json") or {}
    else:
        form = await request.form()
        method = str(form.get("method") or "")
        raw_params = str(form.get("param_json") or "{}")

    if isinstance(raw_params, str):
        try:
            params = json.loads(raw_params)
        except json.JSONDecodeError:
            return {"err_no": 40002, "err_msg": "param_json 不是合法 JSON", "data": None}
    else:
        params = raw_params

    if not method:
        return {"err_no": 40002, "err_msg": "缺少 method 参数", "data": None}
    if not isinstance(params, dict):
        return {"err_no": 40002, "err_msg": "param_json 必须是对象", "data": None}
    return await handle_doudian_method(method, params)
