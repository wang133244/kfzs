# 依赖注入模块：提供统一认证（解析 JWT 获取当前用户）与数据库会话依赖
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import User
from ..security import decode_access_token


bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    # 统一认证依赖：解析 JWT 后从数据库加载用户，失败返回 401
    # 未携带 Authorization 头时直接拒绝
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或凭证已过期",
        )
    try:
        # 解析并校验 JWT，取出用户 ID
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except Exception:
        # token 无效或过期，统一按未登录处理
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或凭证已过期",
        ) from None
    # 按用户 ID 查询数据库，用户已被删除时同样拒绝
    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )
    return user


# 员工权限依赖：仅允许 staff / admin 角色访问，顾客角色返回 403
async def get_current_staff(user: User = Depends(get_current_user)) -> User:
    if user.role not in ("staff", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="该功能仅限内部员工使用",
        )
    return user
