"""Transparent, configurable priority engine.

Score = Σ(component × weight), each component normalised to 0–100:

    severity        0.25   max severity among member reports (1–5 → ×20)
    urgency         0.20   max urgency (1–5 → ×20)
    population      0.20   log-scaled affected-population estimate
    density         0.15   number of citizen reports
    accessibility   0.10   category impact mapping
    safety          0.10   keyword-based safety-risk scan

Weights live in simulation_parameters ('priority.weights') so administrators
can tune them without code changes. The full component breakdown is stored on
the problem row and returned by the API – every score is explainable.
"""
import math

from sqlalchemy.orm import Session

from app.ai.severity_rules import safety_hits
from app.models.civic import ClusterReport, ProblemCluster, Report
from app.models.system import SimulationParameter

DEFAULT_WEIGHTS = {
    "severity": 0.25,
    "urgency": 0.20,
    "population": 0.20,
    "density": 0.15,
    "accessibility": 0.10,
    "safety": 0.10,
}
LEVEL_THRESHOLDS = {"low": 39, "medium": 59, "high": 79}  # above high => critical

# Planning insight: how strongly each category impacts citizen access/mobility.
CATEGORY_ACCESS_IMPACT = {
    "healthcare": 95, "water": 85, "roads": 75, "electricity": 70,
    "public_safety": 70, "drainage": 60, "sanitation": 60, "garbage": 55,
    "street_lighting": 55, "education": 50, "public_transport": 45,
    "environment": 40, "other": 30,
}


def get_weights(db: Session) -> dict:
    row = db.get(SimulationParameter, "priority.weights")
    weights = dict(DEFAULT_WEIGHTS)
    if row and isinstance(row.value_json, dict):
        for k in weights:
            try:
                v = float(row.value_json.get(k, weights[k]))
                weights[k] = max(0.0, min(1.0, v))
            except (TypeError, ValueError):
                pass
    total = sum(weights.values()) or 1.0
    return {k: v / total for k, v in weights.items()}


def _population_component(population_est: int) -> float:
    if population_est <= 0:
        return 0.0
    return min(100.0, round(math.log10(population_est + 1) * 33.3, 1))


def level_for_score(score: float, thresholds: dict | None = None) -> str:
    th = thresholds or LEVEL_THRESHOLDS
    if score <= th["low"]:
        return "low"
    if score <= th["medium"]:
        return "medium"
    if score <= th["high"]:
        return "high"
    return "critical"


def compute_breakdown(db: Session, cluster: ProblemCluster) -> dict:
    """Compute the full explainable breakdown without persisting."""
    weights = get_weights(db)

    texts = [
        f"{r.title} {r.description or ''}"
        for r in db.scalars(
            select_reports_for(cluster.id)
        ).all()
    ]
    combined_text = " ".join(texts)[:4000]

    severity_value = float(cluster.severity) * 20.0
    urgency_value = float(cluster.urgency) * 20.0
    population_value = _population_component(cluster.affected_population_est)
    density_value = min(100.0, cluster.report_count * 15.0)

    cat_slug = cluster.category.slug if cluster.category else "other"
    accessibility_value = float(CATEGORY_ACCESS_IMPACT.get(cat_slug, 40))
    safety_value = min(100.0, 20.0 + safety_hits(combined_text) * 16.0)

    values = {
        "severity": severity_value,
        "urgency": urgency_value,
        "population": population_value,
        "density": density_value,
        "accessibility": accessibility_value,
        "safety": safety_value,
    }

    notes = {
        "severity": f"severity level {cluster.severity}/5",
        "urgency": f"urgency level {cluster.urgency}/5",
        "population": f"~{cluster.affected_population_est} people estimated affected",
        "density": f"{cluster.report_count} citizen report(s)",
        "accessibility": f"category impact weight for '{cat_slug}'",
        "safety": "keyword scan of complaint texts",
    }

    components = {}
    score = 0.0
    for name, value in values.items():
        w = weights[name]
        contribution = round(value * w, 2)
        components[name] = {
            "value": round(value, 1),
            "weight": w,
            "contribution": contribution,
            "note": notes[name],
        }
        score += contribution

    score = round(max(0.0, min(100.0, score)), 1)
    level = level_for_score(score)

    explanations = [
        f"{name.replace('_', ' ').title()}: {c['value']:.0f}/100 × weight {c['weight']:.2f} "
        f"→ {c['contribution']:.1f} pts ({c['note']})"
        for name, c in components.items()
    ]

    return {
        "score": score,
        "level": level,
        "weights_used": weights,
        "components": components,
        "explanations": explanations,
        "engine_version": "weighted-v1",
    }


def apply_priority(db: Session, cluster: ProblemCluster) -> dict:
    """Compute and persist priority on the cluster."""
    breakdown = compute_breakdown(db, cluster)
    cluster.priority_score = breakdown["score"]
    cluster.priority_level = breakdown["level"]
    cluster.priority_components = {
        "components": breakdown["components"],
        "weights_used": breakdown["weights_used"],
        "explanations": breakdown["explanations"],
        "engine_version": breakdown["engine_version"],
    }
    return breakdown


# Local import to avoid a circular import at module import time.
def select_reports_for(cluster_id: str):
    from sqlalchemy import select

    return (
        select(Report)
        .join(ClusterReport, ClusterReport.report_id == Report.id)
        .where(ClusterReport.cluster_id == cluster_id)
        .limit(50)
    )
