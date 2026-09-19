"""Analytics aggregations – every number comes from live database queries."""
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.models.civic import ProblemCluster, Report
from app.models.user import User
from app.models.work import Action, Verification


def overview(db: Session) -> dict:
    total_reports = db.scalar(select(func.count(Report.id)).where(Report.deleted_at.is_(None))) or 0
    open_statuses = ("new", "action_required", "reopened")
    critical = db.scalar(
        select(func.count(ProblemCluster.id)).where(
            ProblemCluster.priority_level == "critical",
            ProblemCluster.status.notin_(("verified", "closed")),
        )
    ) or 0
    action_required = db.scalar(
        select(func.count(ProblemCluster.id)).where(ProblemCluster.status.in_(open_statuses))
    ) or 0
    resolved = db.scalar(
        select(func.count(ProblemCluster.id)).where(ProblemCluster.status.in_(("verified", "closed")))
    ) or 0
    active_problems = db.scalar(
        select(func.count(ProblemCluster.id)).where(
            ProblemCluster.status.notin_(("verified", "closed"))
        )
    ) or 0

    now = utcnow()
    last7 = now - timedelta(days=7)
    new_reports_7d = db.scalar(
        select(func.count(Report.id)).where(Report.created_at >= last7, Report.deleted_at.is_(None))
    ) or 0
    citizens = db.scalar(select(func.count(User.id)).join(User.role).where(User.role.has(name="citizen"))) or 0

    return {
        "total_reports": total_reports,
        "critical_issues": critical,
        "action_required": action_required,
        "resolved": resolved,
        "active_problems": active_problems,
        "new_reports_7d": new_reports_7d,
        "registered_citizens": citizens,
    }


def trends(db: Session, days: int = 14) -> list[dict]:
    since = (utcnow() - timedelta(days=days)).date()
    rows = db.execute(
        select(func.date(Report.created_at), func.count(Report.id))
        .where(Report.created_at >= since, Report.deleted_at.is_(None))
        .group_by(func.date(Report.created_at))
        .order_by(func.date(Report.created_at))
    ).all()
    by_day = {str(r[0]): int(r[1]) for r in rows}
    out = []
    d = since
    today = utcnow().date()
    while d <= today:
        out.append({"date": str(d), "count": by_day.get(str(d), 0)})
        d += timedelta(days=1)
    return out


def by_category(db: Session) -> list[dict]:
    rows = db.execute(
        select(func.coalesce(ProblemCluster.category_id, "none"), func.count())
        .group_by(ProblemCluster.category_id)
    ).all()
    from app.models.catalog import Category

    cats = {c.id: c for c in db.scalars(select(Category)).all()}
    out = []
    for cid, n in rows:
        cat = cats.get(cid)
        out.append({
            "category": cat.slug if cat else "unknown",
            "name": cat.name if cat else "Uncategorised",
            "count": int(n),
            "color": cat.color if cat else "#64748b",
        })
    return sorted(out, key=lambda x: -x["count"])


def department_performance(db: Session) -> list[dict]:
    from sqlalchemy import case

    rows = db.execute(
        select(
            Action.department_id,
            func.count(Action.id),
            func.sum(case((Action.status == "closed", 1), else_=0)),
            func.avg(
                func.extract("epoch", Action.completed_at - Action.created_at) / 3600.0
            ),
        ).group_by(Action.department_id)
    ).all()
    from app.models.catalog import Department

    depts = {d.id: d for d in db.scalars(select(Department)).all()}
    return [
        {
            "department": depts[did].name if did in depts else str(did),
            "total_actions": int(total),
            "completed": int(done),
            "avg_resolution_hours": round(float(hrs), 1) if hrs is not None else None,
        }
        for did, total, done, hrs in rows
    ]


def verification_stats(db: Session) -> dict:
    rows = db.execute(select(Verification.verdict, func.count())).all()
    counts = {v: int(n) for v, n in rows}
    yes, no = counts.get("yes", 0), counts.get("no", 0)
    rate = round(yes / (yes + no) * 100, 1) if (yes + no) else None
    return {"confirmed": yes, "rejected": no, "partial": counts.get("partial", 0), "success_rate": rate}


def resolution_time(db: Session) -> dict | None:
    row = db.execute(
        select(
            func.avg(
                func.extract("epoch", ProblemCluster.resolved_at - ProblemCluster.first_reported_at) / 3600.0
            )
        ).where(ProblemCluster.resolved_at.isnot(None))
    ).scalar()
    return {"avg_resolution_hours": round(float(row), 1)} if row is not None else None


def full_analytics(db: Session) -> dict:
    return {
        "overview": overview(db),
        "trends": trends(db),
        "by_category": by_category(db),
        "departments": department_performance(db),
        "verification": verification_stats(db),
        "resolution_time": resolution_time(db),
    }
