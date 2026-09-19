"""Catalog endpoints: categories & departments (public read / admin write)."""
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import AdminUser, CurrentUser, DbDep, role_name
from app.models.catalog import Category, Department
from app.models.system import AuditLog
from app.schemas.misc import CategoryIn, CategoryOut, DepartmentIn, DepartmentOut
from app.services.audit import record_audit

router = APIRouter(prefix="/catalog", tags=["catalog"])


# ---------------- Categories -----------------
@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: DbDep, user: CurrentUser, include_inactive: bool = False):
    stmt = select(Category).order_by(Category.display_order)
    if not include_inactive:
        stmt = stmt.where(Category.is_active.is_(True))
    return [CategoryOut.model_validate(c) for c in db.scalars(stmt).all()]


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(payload: CategoryIn, db: DbDep, user: AdminUser):
    exists = db.scalar(select(Category).where(Category.slug == payload.slug))
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "slug already exists")
    cat = Category(**payload.model_dump())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    record_audit(str(user.id), role_name(user), "category.create", "category", str(cat.id), after=payload.model_dump())
    db.commit()
    return CategoryOut.model_validate(cat)


@router.patch("/categories/{category_id}", response_model=CategoryOut)
def update_category(category_id: str, payload: dict, db: DbDep, user: AdminUser):
    cat = db.get(Category, category_id)
    if not cat:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    before = {"name": cat.name, "is_active": cat.is_active}
    allowed = {"name", "icon", "color", "display_order", "is_active", "department_id"}
    for k, v in payload.items():
        if k in allowed:
            setattr(cat, k, v)
    db.commit()
    record_audit(str(user.id), role_name(user), "category.update", "category", str(cat.id),
                 before=before, after=payload)
    db.commit()
    return CategoryOut.model_validate(cat)


# ---------------- Departments ----------------
@router.get("/departments", response_model=list[DepartmentOut])
def list_departments(db: DbDep, user: CurrentUser):
    return [DepartmentOut.model_validate(d) for d in db.scalars(select(Department)).all()]


@router.post("/departments", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
def create_department(payload: DepartmentIn, db: DbDep, user: AdminUser):
    exists = db.scalar(select(Department).where(Department.slug == payload.slug))
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "slug already exists")
    dept = Department(**payload.model_dump())
    db.add(dept)
    db.commit()
    db.refresh(dept)
    record_audit(str(user.id), role_name(user), "department.create", "department", str(dept.id), after=payload.model_dump())
    db.commit()
    return DepartmentOut.model_validate(dept)
