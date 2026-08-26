from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from .config import settings


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")  # 密码哈希统一入口


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def create_access_token(user_id: int, role: str, expire_minutes: int | None = None) -> str:
    # 签发 JWT；微信登录可传入更长有效期以便记住用户
    minutes = settings.jwt_expire_minutes if expire_minutes is None else expire_minutes
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {"sub": str(user_id), "role": role, "exp": expires_at}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    # 校验签名与过期时间，失败抛出 jwt 异常
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
