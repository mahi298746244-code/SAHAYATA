"""Problem cluster endpoints."""
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func as sa_func
from sqlalchemy import select

from app.api.deps import AuthorityUser, CurrentUser, DbDep, role_name
from app.db.base import utcnow
from app.models.catalog import Category
from app.models.civic import ProblemCluster, Report
from app.models.system import AuditLog
from app.schemas.civic import ActionOut, ProblemDetail, ProblemOut, ReportBrief, ReportOut
from app.services.notify import notify
from app.services.priority import apply_priority

router = APIRouter(prefix="/problems", tags=["problems"])

OPEN_STATUSES = ("new", "action_required", "assigned", "in_progress", "verification_pending", "reopened")


def _problem_out(c: ProblemCluster) -> dict:
    return {
        "id": str(c.id), "code": c.code, "title": c.title, "status": c.status,
        "subcategory": c.subcategory,
        "latitude": c.latitude, "longitude": c.longitude,
        "address_text": c.address_text, "ward": c.ward,
        "severity": c.severity, "urgency": c.urgency,
        "priority_score": c.priority_score, "priority_level": c.priority_level,
        "affected_population_est": c.affected_population_est,
        "report_count": c.report_count,
        "assigned_department_id": str(c.assigned_department_id) if c.assigned_department_id else None,
        "assigned_department_name": c.assigned_department.name if c.assigned_department else None,
        "first_reported_at": c.first_reported_at, "last_reported_at": c.last_reported_at,
        "is_demo": c.is_demo,
    }


@router.get("")
def list_problems(
    db: DbDep,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_: str | None = Query(None, alias="status"),
    category: str | None = None,
    priority_level: str | None = None,
    q: str | None = None,
):
    stmt = select(ProblemCluster)
    if status_:
        stmt = stmt.where(ProblemCluster.status == status_)
    if category:
        cat = db.scalar(select(Category).where(Category.slug == category))
        if not cat:
            return {"items": [], "total": 0, "page": page, "page_size": page_size}
        stmt = stmt.where(ProblemCluster.category_id == cat.id)
    if priority_level:
        stmt = stmt.where(ProblemCluster.priority_level == priority_level)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(
            sa_func.lower(ProblemCluster.title).like(like)
            | sa_func.lower(sa_func.coalesce(ProblemCluster.address_text, "")).like(like)
            | sa_func.lower(ProblemCluster.code).like(like)
        )
    total = db.scalar(select(sa_func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(ProblemCluster.priority_score.desc(), ProblemCluster.last_reported_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {"items": [_problem_out(c) for c in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/{code}", response_model=ProblemDetail)
def get_problem(code: str, db: DbDep, user: CurrentUser):
    cluster = db.scalar(select(ProblemCluster).where(ProblemCluster.code == code))
    if not cluster:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Problem not found")

    base = _problem_out(cluster)
    base.update({
        "category_slug": cluster.category.slug if cluster.category else None,
        "category_name": cluster.category.name if cluster.category else None,
        "priority_components": cluster.priority_components,
    })

    member_rows = db.scalars(select(Report).where(Report.cluster_id == cluster.id).order_by(Report.created_at)).all()
    base["reports"] = [
        ReportBrief(
            id=str(r.id), code=r.code, title=r.title, description=r.description,
            status=r.status,
            category_id=str(r.category_id) if r.category_id else None,
            category_name=r.category.name if r.category else None,
            subcategory=r.subcategory, category_source=r.category_source,
            ai_confidence=r.ai_confidence, ai_severity=r.ai_severity,
            ai_urgency=r.ai_urgency, ai_keywords=r.ai_keywords, ai_status=r.ai_status,
            latitude=r.latitude, longitude=r.longitude, address_text=r.address_text,
            landmark=r.landmark, ward=r.ward, cluster_code=cluster.code,
            is_public=r.is_public, is_demo=r.is_demo,
            created_at=r.created_at, updated_at=r.updated_at,
            media=list(r.media),
        ).model_dump()
        for r in member_rows
    ]

    from app.models.work import Action

    actions = db.scalars(select(Action).where(Action.cluster_id == cluster.id).order_by(Action.created_at)).all()
    base["actions"] = [ActionOut.model_validate(a).model_dump() for a in actions]
    return base


@router.patch("/{code}/assign")
def assign_problem(code: str, payload: dict, db: DbDep, user: AuthorityUser):
    cluster = db.scalar(select(ProblemCluster).where(ProblemCluster.code == code))
    if not cluster:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Problem not found")
    dept_id = payload.get("department_id")
    if not dept_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "department_id required")

    from app.models.catalog import Department

    dept = db.get(Department, dept_id)
    if not dept:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "unknown department")

    before_status = cluster.status
    cluster.assigned_department_id = dept.id
    cluster.status = "assigned"
    db.commit()

    db.add(AuditLog(
        actor_id=str(user.id), actor_role=role_name(user),
        action="problem.assign", entity_type="problem_cluster", entity_id=cluster.code,
        before={"status": before_status, "department": None},
        after={"status": "assigned", "department": dept.name},
        reason=payload.get("reason"),
    ))
    db.commit()

    reporter_ids = {str(r.citizen_id) for r in db.scalars(select(Report).where(Report.cluster_id == cluster.id)).all() if r.citizen_id}
    notify(reporter_ids, "status_changed", f"Action started on {cluster.code}",
           f"Your reported problem '{cluster.title}' has been assigned to {dept.name}.",
           {"problem_code": cluster.code})
    return {"ok": True, "status": cluster.status}


@router.patch("/{code}/status")
def update_status(code: str, payload: dict, db: DbDep, user: AuthorityUser):
    """Authority-controlled lifecycle moves (close/reopen/manual verify etc.)."""
    cluster = db.scalar(select(ProblemCluster).where(ProblemCluster.code == code))
    if not cluster:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Problem not found")
    new_status = payload.get("status")
    allowed = {"new", "action_required", "assigned", "in_progress",
               "verification_pending", "verified", "closed", "reopened"}
    if new_status not in allowed:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid status")

    before = cluster.status
    cluster.status = new_status
    if new_status == "verified":
        cluster.resolved_at = utcnow()
        _set_member_reports(db, cluster.id, "verified")
    elif new_status == "closed":
        cluster.resolved_at = cluster.resolved_at or utcnow()
        _set_member_reports(db, cluster.id, "closed")
    elif new_status == "reopened":
        cluster.resolved_at = None
        _set_member_reports(db, cluster.id, "reopened")
    db.commit()

    db.add(AuditLog(
        actor_id=str(user.id), actor_role=role_name(user),
        action="problem.status_change", entity_type="problem_cluster", entity_id=cluster.code,
        before={"status": before}, after={"status": new_status}, reason=payload.get("reason"),
    ))
    db.commit()
    return {"ok": True, "status": cluster.status}


@router.post("/{code}/recalculate-priority")
def recalculate_priority(code: str, db: DbDep, user: AuthorityUser):
    cluster = db.scalar(select(ProblemCluster).where(ProblemCluster.code == code))
    if not cluster:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Problem not found")
    breakdown = apply_priority(db, cluster)
    db.commit()
    return {"ok": True, "score": breakdown["score"], "level": breakdown["level"],
            "explanations": breakdown["explanations"]}


def _set_member_reports(db, cluster_id, new_status: str) -> None:
    for r in db.scalars(select(Report).where(Report.cluster_id == cluster_id)).all():
        r.status = new_status
