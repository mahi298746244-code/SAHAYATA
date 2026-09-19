"""Global search across reports, problems, citizens (staff), departments."""
from fastapi import APIRouter, Query
from sqlalchemy import func, or_, select

from app.api.deps import CurrentUser, DbDep, role_name

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
def global_search(db: DbDep, user: CurrentUser, q: str = Query(min_length=2, max_length=120),
                  page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=50)):
    from app.models.civic import ProblemCluster, Report

    like = f"%{q.lower()}%"
    staff = role_name(user) in ("authority", "admin")
    offset = (page - 1) * page_size

    rep_stmt = select(Report).where(
        Report.deleted_at.is_(None),
        or_(
            func.lower(Report.title).like(like),
            func.lower(func.coalesce(Report.description, "")).like(like),
            func.lower(Report.code).like(like),
            func.lower(func.coalesce(Report.address_text, "")).like(like),
        ),
    )
    if not staff:
        rep_stmt = rep_stmt.where(Report.is_public.is_(True) | (Report.citizen_id == str(user.id)))

    prob_stmt = select(ProblemCluster).where(or_(
        func.lower(ProblemCluster.title).like(like),
        func.lower(ProblemCluster.code).like(like),
    ))

    reports = db.scalars(rep_stmt.order_by(Report.created_at.desc()).offset(offset).limit(page_size)).all()
    problems = db.scalars(prob_stmt.order_by(ProblemCluster.priority_score.desc()).offset(offset).limit(page_size)).all()

    rep_total = db.scalar(select(func.count()).select_from(rep_stmt.subquery())) or 0
    prob_total = db.scalar(select(func.count()).select_from(prob_stmt.subquery())) or 0

    return {
        "total": int(rep_total) + int(prob_total),
        "page": page,
        "page_size": page_size,
        "reports": [
            {"code": r.code, "title": r.title[:100], "status": r.status,
             "created_at": r.created_at.isoformat()}
            for r in reports
        ],
        "problems": [
            {"code": c.code, "title": c.title[:100], "status": c.status,
             "priority_level": c.priority_level}
            for c in problems
        ],
    }
