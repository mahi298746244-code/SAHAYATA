"""Duplicate detection & problem clustering.

A ProblemCluster represents one real-world issue that may hold many citizen
reports. A new report joins an existing cluster only when BOTH:
  - it is geographically close (category-aware radius), AND
  - its text is sufficiently similar to the cluster's representative text.

Two different potholes in the same city therefore stay separate problems.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import embeddings
from app.core.config import settings
from app.db.base import utcnow
from app.models.civic import ClusterReport, ProblemCluster, Report
from app.models.catalog import Category
from app.services.geo import find_nearby, haversine_m
from app.services.ids import next_code
from app.services.notify import notify
from app.services.priority import apply_priority

DEFAULT_RADIUS_M = settings.CLUSTER_RADIUS_M_DEFAULT
TEXT_THRESHOLD = settings.CLUSTER_TEXT_SIMILARITY_THRESHOLD
TIME_WINDOW_DAYS = settings.CLUSTER_TIME_WINDOW_DAYS
POPULATION_PER_REPORT = 40  # configurable planning assumption

# Area-level problems (water/drainage) justify wider radii than point defects
# (a pothole). Two different potholes across town therefore never merge.
CATEGORY_RADIUS_M = {
    "roads": 150, "street_lighting": 150, "electricity": 150,
    "garbage": 250, "sanitation": 250, "drainage": 300, "water": 300,
    "healthcare": 300, "education": 200, "public_transport": 200,
    "public_safety": 200, "environment": 200, "other": 150,
}


def _aware(dt: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; treat them as UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _radius_for(category: Category | None) -> int:
    if category:
        return CATEGORY_RADIUS_M.get(category.slug, DEFAULT_RADIUS_M)
    return DEFAULT_RADIUS_M


def cluster_title(report: Report, category: Category | None) -> str:
    cat_name = category.name if category else "Issue"
    place = report.landmark or report.address_text or report.ward or "Local Area"
    return f"{cat_name} – {place[:120]}"


def attach_report(db: Session, report: Report) -> tuple[ProblemCluster | None, float]:
    """Try to join an existing open cluster; otherwise create a new one."""
    now = utcnow()
    window_start = now - timedelta(days=TIME_WINDOW_DAYS)
    category = report.category or report.ai_category
    new_text = f"{report.title} {report.description or ''}"

    candidates = find_nearby(
        db,
        ProblemCluster,
        report.latitude,
        report.longitude,
        radius_m=_radius_for(category) * 3,  # generous prefilter; scored below
        filters=None,
    )
    radius = _radius_for(category)

    best: tuple[ProblemCluster, float] | None = None
    for cluster, dist in candidates:
        if cluster.status in ("verified", "closed"):
            continue
        last_seen = _aware(cluster.last_reported_at)
        if last_seen and last_seen < window_start:
            continue

        same_category = (not category) or (not cluster.category_id) or (
            cluster.category_id == category.id
        )
        sim = embeddings.similarity(new_text, _cluster_text(db, cluster))
        geo_score = max(0.0, 1.0 - (dist / radius)) if radius else 1.0
        # recency: reports seen in the last week cluster more eagerly
        age_days = (now - last_seen).days if last_seen else TIME_WINDOW_DAYS
        time_score = 1.0 if age_days <= 7 else max(0.3, 1.0 - age_days / TIME_WINDOW_DAYS)

        if same_category:
            # Civic duplicates are primarily LOCATION-based: two citizens rarely
            # word a complaint alike, but the same broken pipe is always in the
            # same place. Geography dominates; text guards against unrelated
            # categories being dumped together; far-apart reports can never
            # reach the threshold because geo_score decays to zero.
            #   geo 55% + text 20% + category 15% + recency 10%
            score = geo_score * 0.55 + sim * 0.20 + 0.15 + 0.10 * time_score
            if dist > radius:
                score *= 0.4  # outside strict radius → strongly penalise
        else:
            # Cross-category joins need near-identical text AND close location.
            if sim < TEXT_THRESHOLD + 0.15 or dist > radius:
                continue
            score = sim * 0.7 + geo_score * 0.3

        if best is None or score > best[1]:
            best = (cluster, score)

    if best and best[1] >= TEXT_THRESHOLD:
        cluster, score = best
        db.add(
            ClusterReport(
                cluster_id=cluster.id,
                report_id=report.id,
                similarity=round(score, 3),
                distance_m=haversine_m(
                    cluster.latitude, cluster.longitude, report.latitude, report.longitude
                ),
            )
        )
        report.cluster_id = cluster.id
        _refresh_cluster(db, cluster)
    else:
        cluster = ProblemCluster(
            code=next_code(db, "cluster"),
            title=cluster_title(report, category),
            category_id=(category.id if category else None),
            subcategory=report.subcategory,
            representative_report_id=report.id,
            latitude=report.latitude,
            longitude=report.longitude,
            radius_m=radius,
            address_text=report.address_text,
            ward=report.ward,
            severity=int(report.ai_severity or 2),
            urgency=int(report.ai_urgency or 2),
            affected_population_est=POPULATION_PER_REPORT,
            first_reported_at=now,
            last_reported_at=now,
            is_demo=report.is_demo,
        )
        db.add(cluster)
        db.flush()
        db.add(ClusterReport(cluster_id=cluster.id, report_id=report.id, similarity=1.0, distance_m=0.0))
        report.cluster_id = cluster.id
        _refresh_cluster(db, cluster)

    if report.status in ("reported", "reopened"):
        report.status = "clustered"

    pending_notify = {
        "recipients": _reporter_ids(db, cluster),
        "code": cluster.code,
        "title": cluster.title,
        "report_title": report.title,
    }

    db.commit()

    # Notify after commit – notify() uses its own DB session and would
    # otherwise block on this session's write lock (SQLite single-writer).
    notify(
        pending_notify["recipients"],
        "clustered",
        "Report linked to a known problem",
        f"Your report '{pending_notify['report_title']}' was grouped under "
        f"{pending_notify['code']} ({pending_notify['title']}). You will be notified about progress.",
        {"problem_code": pending_notify["code"]},
    )
    return cluster, (best[1] if best else 1.0)


def _cluster_text(db: Session, cluster: ProblemCluster) -> str:
    rep = db.get(Report, cluster.representative_report_id) if cluster.representative_report_id else None
    if rep:
        return f"{rep.title} {rep.description or ''}"
    return cluster.title


def _reporter_ids(db: Session, cluster: ProblemCluster) -> set[str]:
    rows = db.execute(
        select(Report.citizen_id).join(
            ClusterReport, ClusterReport.report_id == Report.id
        ).where(ClusterReport.cluster_id == cluster.id)
    ).all()
    return {r[0] for r in rows if r[0]}


def _refresh_cluster(db: Session, cluster: ProblemCluster) -> None:
    db.flush()  # sessions run with autoflush=False; make pending links visible
    """Recompute aggregates from member reports, then re-score priority."""
    members = db.scalars(select(Report).where(Report.cluster_id == cluster.id)).all()
    cluster.report_count = len(members) + 0 if members else 1

    severities = [r.ai_severity for r in members if r.ai_severity]
    urgencies = [r.ai_urgency for r in members if r.ai_urgency]
    cluster.severity = max(severities) if severities else max(int(cluster.severity or 2), 2)
    cluster.urgency = max(urgencies) if urgencies else max(int(cluster.urgency or 2), 2)
    cluster.affected_population_est = max(POPULATION_PER_REPORT, cluster.report_count * POPULATION_PER_REPORT)

    lats = [r.latitude for r in members] or [cluster.latitude]
    lngs = [r.longitude for r in members] or [cluster.longitude]
    cluster.latitude = sum(lats) / len(lats)
    cluster.longitude = sum(lngs) / len(lngs)
    aware_members = [_aware(r.created_at) for r in members]
    aware_members = [d for d in aware_members if d is not None]
    cluster.last_reported_at = max(aware_members, default=_aware(cluster.created_at) or utcnow())

    # Keep the newest report as the cluster's text representative so
    # duplicate checks compare against current citizen wording.
    if members:
        latest = max(members, key=lambda r: _aware(r.created_at) or utcnow())
        cluster.representative_report_id = latest.id

    if cluster.status in ("new",):
        cluster.status = "action_required"
    elif cluster.status in ("reopened",):
        cluster.status = "action_required"

    apply_priority(db, cluster)


def recompute_cluster(db: Session, cluster: ProblemCluster) -> None:
    _refresh_cluster(db, cluster)
