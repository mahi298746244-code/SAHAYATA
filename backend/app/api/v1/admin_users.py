"""Admin user management + audit log viewing."""
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import AdminUser, DbDep
from app.models.system import AuditLog
from app.models.user import Role, User
from app.schemas.auth import UserAdminUpdate, UserOut
from app.services.audit import record_audit

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
def list_users(
    db: DbDep,
    user: AdminUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    role: str | None = None,
    q: str | None = None,
):
    stmt = select(User).where(User.deleted_at.is_(None))
    if role:
        r = db.scalar(select(Role).where(Role.name == role))
        if not r:
            return {"items": [], "total": 0, "page": page, "page_size": page_size}
        stmt = stmt.where(User.role_id == r.id)
    if q:
        like = f"%{q.lower()}%"
        from sqlalchemy import func as f

        stmt = stmt.where(f.lower(User.email).like(like) | f.lower(User.full_name).like(like))
    from sqlalchemy import func as f

    total = db.scalar(select(f.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    items = []
    for u in rows:
        items.append({
            "id": str(u.id), "email": u.email, "full_name": u.full_name,
            "phone": u.phone, "role": u.role.name if u.role else "?",
            "department_id": str(u.department_id) if u.department_id else None,
            "department_name": u.department.name if u.department else None,
            "ward": u.ward, "is_active": u.is_active, "is_demo": u.is_demo,
            "created_at": u.created_at.isoformat(),
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/users/authority", status_code=status.HTTP_201_CREATED)
def create_authority(payload: dict, db: DbDep, user: AdminUser):
    """Create authority accounts (never via public register)."""
    from app.core.security import hash_password
    from pydantic import EmailStr

    email = str(payload.get("email", "")).lower().strip()
    full_name = str(payload.get("full_name", "")).strip()
    password = payload.get("password") or ""
    department_id = payload.get("department_id")

    if not email or not full_name or len(password) < 8:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "email, full_name and password(8+) required")
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "email exists")
    auth_role = db.scalar(select(Role).where(Role.name == "authority"))
    dept = None
    if department_id:
        from app.models.catalog import Department

        dept = db.get(Department, department_id)
        if not dept:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "unknown department")

    u = User(email=email, full_name=full_name, password_hash=hash_password(password),
             role_id=auth_role.id, department_id=dept.id if dept else None)
    db.add(u)
    db.commit()
    record_audit(str(user.id), "admin", "user.create_authority", "user", str(u.id),
                 after={"email": email, "department": dept.name if dept else None})
    db.commit()
    return {"ok": True, "id": str(u.id)}


@router.patch("/users/{user_id}")
def update_user(user_id: str, payload: UserAdminUpdate, db: DbDep, user: AdminUser):
    target = db.get(User, user_id)
    if not target or target.deleted_at:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    before = {"is_active": target.is_active, "role": target.role.name if target.role else None}

    if payload.is_active is not None:
        target.is_active = payload.is_active
    if payload.role:
        r = db.scalar(select(Role).where(Role.name == payload.role))
        if not r:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "unknown role")
        target.role_id = r.id
    if "department_id" in payload.model_fields_set:
        target.department_id = payload.department_id or None

    db.commit()
    record_audit(str(user.id), "admin", "user.update", "user", user_id, before=before,
                 after=payload.model_dump(exclude_none=True))
    db.commit()
    return {"ok": True}


@router.get("/audit-logs")
def audit_logs(db: DbDep, user: AdminUser, page: int = 1, page_size: int = Query(30, le=200)):
    stmt = select(AuditLog)
    from sqlalchemy import func as f

    total = db.scalar(select(f.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    from app.schemas.misc import AuditLogOut

    return {
        "items": [AuditLogOut.model_validate(r).model_dump(mode="json") for r in rows],
        "total": total, "page": page, "page_size": page_size,
    }
