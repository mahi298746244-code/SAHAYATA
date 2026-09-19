"""Map endpoints: problems, public reports (privacy-aware), facilities and gaps."""
import random

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import DbDep, get_optional_user, role_name
from app.core.config import settings as cfg
from app.models.catalog import Category
from app.models.civic import ProblemCluster, Report
from app.models.geo import AccessibilityGap, Facility
from app.models.user import User

router = APIRouter(prefix="/map", tags=["map"])

OptionalUser = Depends(get_optional_user)


def _jitter(lat: float, lng: float, meters: int) -> tuple[float, float]:
    """Coarse location for public views – protects exact citizen positions."""
    dlat = (random.random() - 0.5) * 2 * (meters / 111_320.0)
    dlng = (random.random() - 0.5) * 2 * (meters / max(1.0, 111_320.0 * math_cos(lat)))
    return round(lat + dlat, 6), round(lng + dlng, 6)


def math_cos(deg: float) -> float:
    import math

    return max(0.2, math.cos(math.radians(deg)))


@router.get("/problems")
def map_problems(
    db: DbDep,
    sw_lat: float = Query(...), sw_lng: float = Query(...),
    ne_lat: float = Query(...), ne_lng: float = Query(...),
    status_: str | None = Query(None, alias="status"),
    category: str | None = None,
    priority_level: str | None = None,
):
    stmt = select(ProblemCluster).where(
        ProblemCluster.latitude.between(sw_lat, ne_lat),
        ProblemCluster.longitude.between(sw_lng, ne_lng),
    )
    if status_:
        stmt = stmt.where(ProblemCluster.status == status_)
    else:
        stmt = stmt.where(ProblemCluster.status.notin_(("verified", "closed")))
    if category:
        cat = db.scalar(select(Category).where(Category.slug == category))
        if cat:
            stmt = stmt.where(ProblemCluster.category_id == cat.id)
    if priority_level:
        stmt = stmt.where(ProblemCluster.priority_level == priority_level)

    rows = db.scalars(stmt.limit(800)).all()
    return [
        {
            "id": c.code, "type": "problem",
            "lat": round(c.latitude, 6), "lng": round(c.longitude, 6),
            "title": c.title, "status": c.status,
            "priority_level": c.priority_level,
            "priority_score": round(c.priority_score, 1),
            "category": c.category.slug if c.category else None,
            "category_color": c.category.color if c.category else "#64748b",
            "report_count": c.report_count,
            "affected_population_est": c.affected_population_est,
        }
        for c in rows
    ]


@router.get("/public-reports")
def map_public_reports(
    db: DbDep,
    user: User | None = OptionalUser,
    sw_lat: float = Query(...), sw_lng: float = Query(...),
    ne_lat: float = Query(...), ne_lng: float = Query(...),
):
    """Individual public reports; coordinates fuzzed unless staff/owner."""
    stmt = select(Report).where(
        Report.is_public.is_(True),
        Report.deleted_at.is_(None),
        Report.latitude.between(sw_lat, ne_lat),
        Report.longitude.between(sw_lng, ne_lng),
    ).limit(600)
    rows = db.scalars(stmt).all()

    staff = user is not None and role_name(user) in ("authority", "admin")
    cluster_map: dict[str, str] = {}
    ids = {str(r.cluster_id) for r in rows if r.cluster_id}
    if ids:
        clusters = db.scalars(select(ProblemCluster).where(ProblemCluster.id.in_(ids))).all()
        cluster_map = {str(c.id): c.code for c in clusters}

    out = []
    for r in rows:
        lat, lng = r.latitude, r.longitude
        owner = user is not None and str(r.citizen_id) == str(user.id)
        if not staff and not owner:
            lat, lng = _jitter(lat, lng, cfg.PUBLIC_COORD_JITTER_M)
        out.append({
            "id": r.code, "type": "report",
            "lat": lat, "lng": lng,
            "title": r.title[:80], "status": r.status,
            "category": r.category.slug if r.category else None,
            "cluster_code": cluster_map.get(str(r.cluster_id)) if r.cluster_id else None,
        })
    return out


@router.get("/facilities")
def map_facilities(
    db: DbDep,
    facility_type: str | None = None,
    sw_lat: float = Query(-90), sw_lng: float = Query(-180),
    ne_lat: float = Query(90), ne_lng: float = Query(180),
):
    stmt = select(Facility).where(
        Facility.latitude.between(sw_lat, ne_lat),
        Facility.longitude.between(sw_lng, ne_lng),
    )
    if facility_type:
        stmt = stmt.where(Facility.facility_type == facility_type)
    rows = db.scalars(stmt.limit(500)).all()
    return [
        {
            "id": str(f.id), "type": "facility",
            "lat": f.latitude, "lng": f.longitude,
            "title": f.name, "facility_type": f.facility_type,
            "subtype": f.subtype, "service_level": f.service_level,
        }
        for f in rows
    ]


@router.get("/gaps")
def map_gaps(db: DbDep, severity: str | None = None):
    stmt = select(AccessibilityGap)
    if severity:
        stmt = stmt.where(AccessibilityGap.severity_label == severity)
    rows = db.scalars(stmt.order_by(AccessibilityGap.gap_score.desc()).limit(300)).all()
    return [
        {
            "id": str(g.id), "type": "gap",
            "lat": g.latitude, "lng": g.longitude,
            "title": g.area_label, "facility_type": g.facility_type,
            "gap_score": g.gap_score, "severity_label": g.severity_label,
            "population_est": g.population_est,
            "nearest_distance_km": g.nearest_distance_km,
            "insight_text": g.insight_text,
        }
        for g in rows
    ]
