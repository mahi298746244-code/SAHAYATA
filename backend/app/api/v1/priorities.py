"""Priority ranking endpoints with full explainability + admin weight control."""
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import AdminUser, AuthorityUser, CurrentUser, DbDep, role_name
from app.models.system import AuditLog, SimulationParameter
from app.services.priority import DEFAULT_WEIGHTS, get_weights

router = APIRouter(prefix="/priorities", tags=["priorities"])


@router.get("")
def ranked_problems(db: DbDep, user: CurrentUser, limit: int = 20, level: str | None = None):
    from app.models.civic import ProblemCluster

    stmt = select(ProblemCluster).where(
        ProblemCluster.status.notin_(("verified", "closed"))
    )
    if level:
        stmt = stmt.where(ProblemCluster.priority_level == level)
    rows = db.scalars(stmt.order_by(ProblemCluster.priority_score.desc()).limit(min(limit, 100))).all()
    return [
        {
            "code": c.code, "title": c.title,
            "score": round(c.priority_score, 1), "level": c.priority_level,
            "status": c.status,
            "category": c.category.slug if c.category else None,
            "report_count": c.report_count,
            "affected_population_est": c.affected_population_est,
            "top_factors": [
                f"{name}: {comp['contribution']:.0f} pts"
                for name, comp in sorted(
                    (c.priority_components or {}).get("components", {}).items(),
                    key=lambda kv: -kv[1]["contribution"],
                )[:3]
            ],
        }
        for c in rows
    ]


@router.get("/weights")
def get_weight_config(db: DbDep, user: AuthorityUser):
    row = db.get(SimulationParameter, "priority.weights")
    return {
        "weights": row.value_json if row else DEFAULT_WEIGHTS,
        "defaults": DEFAULT_WEIGHTS,
        "updated_by_id": str(row.updated_by_id) if row and row.updated_by_id else None,
    }


@router.put("/weights")
def set_weights(payload: dict, db: DbDep, user: AdminUser):
    weights = payload.get("weights") or {}
    cleaned = {}
    for k in DEFAULT_WEIGHTS:
        v = weights.get(k, DEFAULT_WEIGHTS[k])
        try:
            cleaned[k] = max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"invalid weight for {k}") from None
    total = sum(cleaned.values())
    if total <= 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "weights must sum to > 0")

    before_row = db.get(SimulationParameter, "priority.weights")
    before = dict(before_row.value_json) if before_row else None
    row = before_row or SimulationParameter(key="priority.weights", description="Priority engine component weights")
    row.value_json = cleaned
    row.updated_by_id = str(user.id)
    db.add(row)

    from app.services.audit import record_audit

    record_audit(str(user.id), role_name(user), "priority.weights_update",
                 "simulation_parameters", "priority.weights", before=before, after=cleaned,
                 reason=payload.get("reason"))
    db.commit()

    # re-score open problems so rankings reflect new policy immediately
    from app.models.civic import ProblemCluster
    from app.services.priority import apply_priority

    clusters = db.scalars(select(ProblemCluster)).all()
    for c in clusters:
        apply_priority(db, c)
    db.commit()
    return {"ok": True, "weights": cleaned, "rescored": len(clusters)}
