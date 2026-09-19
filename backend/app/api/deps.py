"""FastAPI dependencies: DB session, current user, RBAC guards."""
from typing import Annotated

import jwt as pyjwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import Role, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

DbDep = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbDep,
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> User:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token type")
        user_id = payload["sub"]
    except (pyjwt.ExpiredSignatureError, KeyError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from None
    except pyjwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from None

    user = db.get(User, user_id)
    if user is None or user.deleted_at or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account disabled or missing")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_optional_user(db: DbDep, token: Annotated[str | None, Depends(oauth2_scheme)]) -> User | None:
    if not token:
        return None
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        user = db.get(User, payload["sub"])
        if user and not user.deleted_at and user.is_active:
            return user
    except pyjwt.PyJWTError:
        pass
    return None


def role_name(user: User) -> str:
    return user.role.name if user.role else "citizen"


def require_roles(*roles: str):
    def guard(user: CurrentUser) -> User:
        r = role_name(user)
        # admin inherits authority capabilities
        if r in roles or (r == "admin" and "authority" in roles):
            return user
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")

    return guard


AuthorityUser = Annotated[User, Depends(require_roles("authority"))]
AdminUser = Annotated[User, Depends(require_roles("admin"))]


async def audit_context(request: Request) -> dict:
    """Extract ip/user-agent for audit rows."""
    fwd = request.headers.get("x-forwarded-for")
    ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else None)
    return {"ip": ip, "user_agent": request.headers.get("user-agent")}
