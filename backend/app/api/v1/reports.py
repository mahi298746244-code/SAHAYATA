"""Report endpoints: create (multipart), list, detail, update, similar."""
from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import or_, select

from app.api.deps import CurrentUser, DbDep, get_current_user, get_optional_user, role_name
from app.core.config import settings
from app.db.base import utcnow
from app.models.catalog import Category
from app.models.civic import ClusterReport, ProblemCluster, Report, ReportMedia
from app.models.system import AuditLog
from app.models.user import User
from app.schemas.civic import MediaOut, ReportCreate, ReportDetail, ReportOut, ReportUpdate
from app.services.ids import next_code
from app.services.pipeline import process_report
from app.services.uploads import UploadRejected, store_upload

router = APIRouter(prefix="/reports", tags=["reports"])

EDITABLE_STATUSES = {"reported", "clustered", "reopened"}


def _report_out(r: Report) -> ReportOut:
    return ReportOut(
        id=str(r.id), code=r.code, title=r.title, description=r.description,
        status=r.status, category_id=str(r.category_id) if r.category_id else None,
        category_name=r.category.name if r.category else None,
        subcategory=r.subcategory, category_source=r.category_source,
        ai_confidence=r.ai_confidence, ai_severity=r.ai_severity,
        ai_urgency=r.ai_urgency, ai_keywords=r.ai_keywords, ai_status=r.ai_status,
        latitude=r.latitude, longitude=r.longitude,
        address_text=r.address_text, landmark=r.landmark, ward=r.ward,
        cluster_code=None, is_public=r.is_public, is_demo=r.is_demo,
        created_at=r.created_at, updated_at=r.updated_at,
    )


def _detail_out(db, r: Report, viewer: User | None) -> ReportDetail:
    base = _report_out(r).model_dump()
    cluster_code = None
    if r.cluster_id:
        c = db.get(ProblemCluster, r.cluster_id)
        cluster_code = c.code if c else None
    can_see_private = (
        viewer is not None
        and (role_name(viewer) in ("authority", "admin") or str(viewer.id) == str(r.citizen_id))
    )
    base.update({
        "cluster_code": cluster_code,
        "media": [MediaOut.model_validate(m) for m in r.media],
        "citizen_name": r.citizen.full_name if (can_see_private and r.citizen) else None,
        "contact_phone": r.contact_phone if can_see_private else None,
    })
    return ReportDetail(**base)


@router.post("", response_model=ReportDetail, status_code=status.HTTP_201_CREATED)
async def create_report(
    background: BackgroundTasks,
    db: DbDep,
    user: CurrentUser,
    title: str = Form(...),
    description: str = Form(""),
    latitude: float = Form(...),
    longitude: float = Form(...),
    category_id: str | None = Form(None),
    address_text: str | None = Form(None),
    landmark: str | None = Form(None),
    ward: str | None = Form(None),
    location_source: str = Form("map"),
    contact_phone: str | None = Form(None),
    additional_notes: str | None = Form(None),
    language: str = Form("en"),
    images: list[UploadFile] = File(default=[]),
    videos: list[UploadFile] = File(default=[]),
    audios: list[UploadFile] = File(default=[]),
):
    if location_source not in ("gps", "map", "address"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid location_source")
    # location permission is optional; manual map/address selection is supported.
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid coordinates")

    category = None
    if category_id:
        category = db.get(Category, category_id)
        if not category:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "unknown category_id")

    report = Report(
        code=next_code(db, "report"),
        citizen_id=str(user.id),
        title=title.strip(),
        description=description.strip(),
        category_id=str(category.id) if category else None,
        latitude=latitude,
        longitude=longitude,
        address_text=(address_text or "")[:300] or None,
        landmark=(landmark or "")[:200] or None,
        ward=(ward or "")[:120] or None,
        location_source=location_source,
        contact_phone=(contact_phone or "")[:20] or None,
        additional_notes=(additional_notes or "")[:1000],
        language=language[:8],
    )
    db.add(report)
    db.flush()

    saved_any = False
    for files in (images, videos, audios):
        for f in files[:6]:
            try:
                meta = store_upload(f.file, f.filename or "", f.content_type or "")
            except UploadRejected as exc:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{f.filename}: {exc}") from exc
            db.add(ReportMedia(report_id=report.id, created_by_role="citizen", **meta))
            saved_any = True

    db.commit()
    db.refresh(report)

    background.add_task(process_report, str(report.id))
    return _detail_out(db, report, user)


@router.get("")
def list_reports(
    db: DbDep,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_: str | None = Query(None, alias="status"),
    category: str | None = None,
    q: str | None = None,
    mine_only: bool = False,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
):
    role = role_name(user)
    stmt = select(Report).where(Report.deleted_at.is_(None))
    if role == "citizen" or mine_only:
        stmt = stmt.where(Report.citizen_id == str(user.id))

    if status_:
        stmt = stmt.where(Report.status == status_)
    if category:
        cat = db.scalar(select(Category).where(Category.slug == category))
        if not cat:
            return {"items": [], "total": 0, "page": page, "page_size": page_size}
        stmt = stmt.where(Report.category_id == cat.id)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func_lower(Report.title).like(like), func_lower(Report.description).like(like), func_lower(func_coalesce_code(db)).like(like)))
    if date_from:
        stmt = stmt.where(Report.created_at >= date_from)
    if date_to:
        stmt = stmt.where(Report.created_at <= date_to)

    total = db.scalar(func_count_from(stmt)) or 0
    rows = db.scalars(stmt.order_by(Report.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()

    items = []
    for r in rows:
        d = _report_out(r).model_dump()
        d["media_count"] = len(r.media)
        items.append(d)

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/mine")
def my_reports(db: DbDep, user: CurrentUser, page: int = 1, page_size: int = 50):
    stmt = select(Report).where(
        Report.citizen_id == str(user.id), Report.deleted_at.is_(None)
    )
    total = db.scalar(func_count_from(stmt)) or 0
    rows = db.scalars(stmt.order_by(Report.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {
        "items": [_report_out(r).model_dump() | {"media_count": len(r.media)} for r in rows],
        "total": total, "page": page, "page_size": page_size,
    }


@router.get("/{code}", response_model=ReportDetail)
def get_report(code: str, db: DbDep, viewer: User | None = Depends(get_optional_user)):
    report = db.scalar(select(Report).where(Report.code == code, Report.deleted_at.is_(None)))
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    role = role_name(viewer) if viewer else None
    is_owner = viewer and str(report.citizen_id) == str(viewer.id)
    if not report.is_public and role not in ("authority", "admin") and not is_owner:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This report is private")
    return _detail_out(db, report, viewer)


@router.patch("/{code}", response_model=ReportDetail)
def update_report(code: str, payload: ReportUpdate, db: DbDep, user: CurrentUser):
    report = db.scalar(select(Report).where(Report.code == code))
    if not report or report.deleted_at:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    role = role_name(user)
    is_owner = str(report.citizen_id) == str(user.id)

    changes: dict[str, dict] = {}
    if payload.category_id and payload.category_id != str(report.category_id):
        if role not in ("authority", "admin"):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only authorities can change category")
        cat = db.get(Category, payload.category_id)
        if not cat:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "unknown category")
        changes["category"] = {"before": str(report.category_id), "after": payload.category_id}
        report.category_id = cat.id
        report.category_source = "admin"
        report.subcategory = report.subcategory  # keep

    editable_fields = {
        "title": payload.title, "description": payload.description,
        "address_text": payload.address_text, "landmark": payload.landmark,
        "additional_notes": payload.additional_notes,
    }
    for field, value in editable_fields.items():
        if value is not None:
            if not (is_owner and report.status in EDITABLE_STATUSES) and role not in ("authority", "admin"):
                raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot edit this report at its current stage")
            before = getattr(report, field)
            if before != value:
                changes.setdefault(field, {})["before"] = before
                changes.setdefault(field, {})["after"] = value
                setattr(report, field, value[:4000] if field == "description" else value)

    if changes:
        db.add(AuditLog(
            actor_id=str(user.id), actor_role=role, action="report.update",
            entity_type="report", entity_id=report.code,
            before={k: v["before"] for k, v in changes.items()},
            after={k: v["after"] for k, v in changes.items()},
        ))
    db.commit()
    db.refresh(report)
    return _detail_out(db, report, user)


@router.delete("/{code}", status_code=status.HTTP_204_NO_CONTENT)
def delete_report(code: str, db: DbDep, user: CurrentUser):
    """Soft-delete own report (spec 6.2); admins may delete any."""
    report = db.scalar(select(Report).where(Report.code == code, Report.deleted_at.is_(None)))
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    role = role_name(user)
    is_owner = str(report.citizen_id) == str(user.id)
    if not is_owner and role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only delete your own reports")
    if is_owner and role != "admin" and report.status in ("closed",):
        raise HTTPException(status.HTTP_409_CONFLICT, "Closed reports cannot be deleted")

    report.deleted_at = utcnow()
    db.add(AuditLog(
        actor_id=str(user.id), actor_role=role, action="report.delete",
        entity_type="report", entity_id=report.code,
        reason="deleted by " + ("admin" if not is_owner else "owner"),
    ))
    db.commit()


@router.get("/{code}/similar")
def similar_reports(code: str, db: DbDep, user: CurrentUser):
    """Reports linked to the same physical problem."""
    report = db.scalar(select(Report).where(Report.code == code))
    if not report or not report.cluster_id:
        return {"cluster": None, "reports": []}
    cluster = db.get(ProblemCluster, report.cluster_id)
    siblings = db.scalars(
        select(Report)
        .join(ClusterReport, ClusterReport.report_id == Report.id)
        .where(ClusterReport.cluster_id == cluster.id, Report.id != report.id)
        .order_by(ClusterReport.similarity.desc())
        .limit(20)
    ).all()
    return {
        "cluster": {"code": cluster.code, "title": cluster.title, "status": cluster.status},
        "reports": [_report_out(s).model_dump() for s in siblings],
    }


# --- small helpers kept local to avoid extra imports noise -------------------
from sqlalchemy import func as _f  # noqa: E402


def func_lower(col):
    return _f.lower(col)


def func_coalesce_code(db):
    return _f.coalesce(Report.code, "")


def func_count_from(stmt):
    from sqlalchemy import func as f, select as _select

    return _select(f.count()).select_from(stmt.subquery())
