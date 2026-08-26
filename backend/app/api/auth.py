# 认证登录相关 API 路由
import json
import secrets
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..config import settings
from ..core.wechat import code_to_openid
from ..db import get_db
from ..models import Order, User
from ..schemas import (
    CartOut,
    CartSaveRequest,
    LoginRequest,
    MyOrderItemOut,
    MyOrderOut,
    ProfileOut,
    ProfileUpdate,
    TokenResponse,
    WechatLoginRequest,
)
from ..security import create_access_token, hash_password, verify_password
from .deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

WECHAT_TOKEN_MINUTES = 60 * 24 * 30
UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads" / "avatars"


def _wallet_float(user: User) -> float:
    return float(user.wallet_balance if user.wallet_balance is not None else settings.initial_wallet)


def _token_response(user: User, expire_minutes: int | None = None) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id, user.role, expire_minutes=expire_minutes),
        role=user.role,
        username=user.username,
        avatar_url=user.avatar_url or "",
        wallet_balance=_wallet_float(user),
        user_id=user.id,
    )


def _login_type(user: User) -> str:
    return "wechat" if user.openid else "password"


async def _unique_username(db: AsyncSession, base: str) -> str:
    cleaned = (base or "").strip() or "微信用户"
    cleaned = cleaned[:48]
    name = cleaned
    index = 1
    while await db.scalar(select(User).where(User.username == name)):
        suffix = f"_{index}"
        name = cleaned[: 64 - len(suffix)] + suffix
        index += 1
    return name


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    # 用户名密码登录，校验 bcrypt 哈希后签发 JWT（保留测试顾客与管理员账号）
    user = await db.scalar(select(User).where(User.username == payload.username))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return _token_response(user)


@router.post("/wechat", response_model=TokenResponse)
async def wechat_login(payload: WechatLoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    # 真实微信登录：code 换 openid；开发者工具未配置 AppSecret 时用 local_key 记住同一用户
    openid = await code_to_openid(payload.code)
    if not openid:
        local_key = (payload.local_key or "").strip()
        if not local_key:
            raise HTTPException(status_code=400, detail="微信登录失败，请重试或使用测试账号")
        openid = "dev:" + local_key[:80]
    user = await db.scalar(select(User).where(User.openid == openid))
    if user is None:
        preferred = (payload.username or "").strip() or f"微信用户_{openid[-6:]}"
        username = await _unique_username(db, preferred)
        user = User(
            username=username,
            password_hash=hash_password(secrets.token_urlsafe(24)),
            role="customer",
            openid=openid,
            avatar_url=(payload.avatar_url or "").strip(),
            wallet_balance=Decimal(str(settings.initial_wallet)),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return _token_response(user, expire_minutes=WECHAT_TOKEN_MINUTES)


@router.get("/me", response_model=ProfileOut)
async def get_me(user: User = Depends(get_current_user)) -> ProfileOut:
    return ProfileOut(
        id=user.id,
        username=user.username,
        role=user.role,
        avatar_url=user.avatar_url or "",
        wallet_balance=_wallet_float(user),
        login_type=_login_type(user),
    )


@router.patch("/me", response_model=ProfileOut)
async def update_me(
    payload: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProfileOut:
    row = await db.get(User, user.id)
    if row is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    if payload.username is not None:
        name = payload.username.strip()
        if not name or len(name) > 32:
            raise HTTPException(status_code=400, detail="用户名长度为 1-32 个字符")
        taken = await db.scalar(select(User).where(User.username == name, User.id != row.id))
        if taken is not None:
            raise HTTPException(status_code=409, detail="用户名已被占用")
        row.username = name
    if payload.avatar_url is not None:
        url = payload.avatar_url.strip()
        if url and not (
            url.startswith("cloud://") or url.startswith("/uploads/") or url.startswith("https://")
        ):
            raise HTTPException(status_code=400, detail="头像地址不合法")
        if len(url) > 512:
            raise HTTPException(status_code=400, detail="头像地址过长")
        row.avatar_url = url
    await db.commit()
    await db.refresh(row)
    return ProfileOut(
        id=row.id,
        username=row.username,
        role=row.role,
        avatar_url=row.avatar_url or "",
        wallet_balance=_wallet_float(row),
        login_type=_login_type(row),
    )


@router.post("/me/avatar", response_model=ProfileOut)
async def upload_avatar(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProfileOut:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="请选择头像图片")
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="头像不能超过 2MB")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{user.id}.jpg"
    (UPLOAD_DIR / filename).write_bytes(content)
    row = await db.get(User, user.id)
    if row is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    row.avatar_url = f"/uploads/avatars/{filename}"
    await db.commit()
    await db.refresh(row)
    return ProfileOut(
        id=row.id,
        username=row.username,
        role=row.role,
        avatar_url=row.avatar_url,
        wallet_balance=_wallet_float(row),
        login_type=_login_type(row),
    )


def _parse_cart(raw: str | None) -> list[dict]:
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


@router.get("/me/cart", response_model=CartOut)
async def get_cart(user: User = Depends(get_current_user)) -> CartOut:
    return CartOut(items=_parse_cart(user.cart_json))


@router.put("/me/cart", response_model=CartOut)
async def save_cart(
    payload: CartSaveRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CartOut:
    row = await db.get(User, user.id)
    if row is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    items = payload.items if isinstance(payload.items, list) else []
    row.cart_json = json.dumps(items, ensure_ascii=False)
    await db.commit()
    await db.refresh(row)
    return CartOut(items=_parse_cart(row.cart_json))


@router.get("/me/orders", response_model=list[MyOrderOut])
async def my_orders(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[MyOrderOut]:
    stmt = (
        select(Order)
        .where(Order.user_id == user.id)
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc())
    )
    orders = list(await db.scalars(stmt))
    result: list[MyOrderOut] = []
    for order in orders:
        result.append(
            MyOrderOut(
                order_id=order.order_id,
                customer=order.customer,
                product=order.product,
                amount=order.amount,
                status=order.status,
                created_at=order.created_at,
                items=[
                    MyOrderItemOut(
                        product_id=item.product_id,
                        title=item.title,
                        price=item.price,
                        quantity=item.quantity,
                    )
                    for item in order.items
                ],
            )
        )
    return result
