"""Authentication endpoints: register, login, refresh, logout, profile."""
from datetime import timedelta, timezone
from typing import Annotated

import jwt as pyjwt
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.base import utcnow
from app.db.session import SessionLocal
from app.models.system import AuditLog
from app.models.user import RefreshToken, Role, User
from app.schemas.auth import (
    LoginIn,
    RefreshIn,
    RegisterIn,
    TokenPair,
    UserAdminUpdate,
    UserOut,
)
from app.api.deps import CurrentUser, DbDep, role_name
from app.services.notify import notify

router = APIRouter(prefix="/auth", tags=["auth"])
log = get_logger("sahayata.auth")


def _issue_tokens(user: User) -> TokenPair:
    access, _ = create_access_token(str(user.id), role_name(user))
    refresh, jti = create_refresh_token(str(user.id))
    with SessionLocal() as db:
        db.add(
            RefreshToken(
                jti=jti,
                user_id=str(user.id),
                expires_at=utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            )
        )
        db.commit()
    return TokenPair(access_token=access, refresh_token=refresh)


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        role=role_name(user),
        department_id=str(user.department_id) if user.department_id else None,
        department_name=user.department.name if user.department else None,
        ward=user.ward,
        preferred_language=user.preferred_language,
        is_active=user.is_active,
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterIn, request: Request, db: DbDep):
    """Public self-registration always creates a CITIZEN account."""
    existing = db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    citizen_role = db.scalar(select(Role).where(Role.name == "citizen"))
    if not citizen_role:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Roles not initialised; run seed script")

    user = User(
        email=payload.email.lower(),
        phone=payload.phone,
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
        role_id=citizen_role.id,
        ward=payload.ward,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    db.add(
        AuditLog(
            actor_id=str(user.id), actor_role="citizen", action="user.register",
            entity_type="user", entity_id=str(user.id),
            ip=request.client.host if request.client else None,
        )
    )
    db.commit()
    notify([str(user.id)], "welcome", "Welcome to SAHAYATA",
           "Your citizen account is ready. You can now report civic issues.")
    log.info("user registered user=%s", user.email)
    return _user_out(user)


@router.post("/login", response_model=TokenPair)
def login_form(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbDep):
    """OAuth2 password flow (used by Swagger UI too)."""
    return _login(db, form.username, form.password)


@router.post("/login-json", response_model=TokenPair)
def login_json(payload: LoginIn, db: DbDep):
    return _login(db, payload.email, payload.password)


def _login(db, email: str, password: str) -> TokenPair:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if not user.is_active or user.deleted_at:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is disabled")
    log.info("login ok user=%s role=%s", user.email, role_name(user))
    return _issue_tokens(user)


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshIn, db: DbDep):
    try:
        claims = decode_token(payload.refresh_token)
    except pyjwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token") from None
    if claims.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong token type")

    row = db.get(RefreshToken, claims["jti"])
    expires_at = row.expires_at if row and row.expires_at.tzinfo else (
        row.expires_at.replace(tzinfo=timezone.utc) if row else None
    )
    if not row or row.revoked_at or (expires_at and expires_at < utcnow()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token revoked or expired")

    user = db.get(User, claims["sub"])
    if not user or not user.is_active or user.deleted_at:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account disabled")

    # rotation: revoke old, issue new pair
    row.revoked_at = utcnow()
    db.commit()
    return _issue_tokens(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: RefreshIn, user: CurrentUser):
    try:
        claims = decode_token(payload.refresh_token)
        with SessionLocal() as db:
            row = db.get(RefreshToken, claims.get("jti", ""))
            if row and row.user_id == str(user.id):
                row.revoked_at = utcnow()
                db.commit()
    except pyjwt.PyJWTError:
        pass


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return _user_out(user)


@router.patch("/me", response_model=UserOut)
def update_me(payload: dict, user: CurrentUser, db: DbDep):
    allowed = {"full_name", "phone", "ward", "preferred_language"}
    for k, v in payload.items():
        if k in allowed:
            setattr(user, k, v)
    db.commit()
    return _user_out(user)
