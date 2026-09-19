"""Facilities CRUD + accessibility gap endpoints."""
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import AdminUser, AuthorityUser, CurrentUser, DbDep, role_name
from app.models.geo import AccessibilityGap, Facility
from app.schemas.misc import FacilityIn, FacilityOut, GapOut
from app.services import accessibility

router = APIRouter(tags=["accessibility"])


@router.get("/facilities", response_model=list[FacilityOut])
def list_facilities(
    db: DbDep,
    user: CurrentUser,
    facility_type: str | None = None,
    limit: int = Query(200, le=1000),
):
    stmt = select(Facility).limit(limit)
    if facility_type:
        stmt = stmt.where(Facility.facility_type == facility_type)
    return [FacilityOut.model_validate(f) for f in db.scalars(stmt).all()]


@router.post("/facilities", response_model=FacilityOut, status_code=status.HTTP_201_CREATED)
def create_facility(payload: FacilityIn, db: DbDep, user: AdminUser):
    f = Facility(**payload.model_dump())
    db.add(f)
    db.commit()
    db.refresh(f)
    from app.services.audit import record_audit

    record_audit(str(user.id), role_name(user), "facility.create", "facility", str(f.id), after=payload.model_dump())
    db.commit()
    return FacilityOut.model_validate(f)


@router.delete("/facilities/{facility_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_facility(facility_id: str, db: DbDep, user: AdminUser):
    f = db.get(Facility, facility_id)
    if not f:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Facility not found")
    db.delete(f)
    db.commit()
    from app.services.audit import record_audit

    record_audit(str(user.id), role_name(user), "facility.delete", "facility", facility_id)
    db.commit()


@router.post("/accessibility/compute")
def compute_gaps(db: DbDep, user: AdminUser):
    created = accessibility.compute_gaps(db, actor_id=str(user.id))
    return {"ok": True, "rows_written": created}


@router.get("/accessibility/gaps", response_model=list[GapOut])
def get_gaps(
    db: DbDep,
    user: CurrentUser,
    facility_type: str | None = None,
    min_severity: int = Query(0, ge=0, le=2),
):
    stmt = select(AccessibilityGap).order_by(AccessibilityGap.gap_score.desc()).limit(300)
    if facility_type:
        stmt = stmt.where(AccessibilityGap.facility_type == facility_type)
    rows = [GapOut.model_validate(g) for g in db.scalars(stmt).all()]
    order = {"none": 0, "moderate": 1, "severe": 2}
    return [g for g in rows if order[g.severity_label] >= min_severity]
