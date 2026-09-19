"""Impact simulator – clearly labelled planning estimates, never real costs."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.civic import ProblemCluster
from app.models.system import SimulationParameter

DEFAULTS = {
    "cost_per_problem": {
        "water": 120000, "healthcare": 250000, "roads": 80000,
        "education": 150000, "sanitation": 60000, "garbage": 45000,
        "street_lighting": 30000, "electricity": 90000, "drainage": 110000,
        "public_safety": 70000, "public_transport": 200000,
        "environment": 50000, "other": 40000,
    },
    "beneficiaries_per_problem": {
        "water": 900, "healthcare": 2500, "roads": 1200, "education": 800,
        "sanitation": 650, "garbage": 500, "street_lighting": 400,
        "electricity": 850, "drainage": 750, "public_safety": 1000,
        "public_transport": 1800, "environment": 600, "other": 350,
    },
}


def get_params(db: Session) -> dict:
    row = db.get(SimulationParameter, "simulator.defaults")
    if row and isinstance(row.value_json, dict):
        merged = {**DEFAULTS}
        for k in ("cost_per_problem", "beneficiaries_per_problem"):
            if isinstance(row.value_json.get(k), dict):
                merged[k] = {**DEFAULTS[k], **row.value_json[k]}
        return merged
    return DEFAULTS


def save_params(db: Session, params: dict, updated_by: str | None) -> None:
    row = db.get(SimulationParameter, "simulator.defaults")
    if not row:
        row = SimulationParameter(key="simulator.defaults", description="Impact simulator assumptions")
        db.add(row)
    row.value_json = params
    row.updated_by_id = updated_by
    db.commit()


def run_simulation(db: Session, budget: float, sectors: list[str]) -> dict:
    """Greedy selection by priority within selected sectors.

    NOTE: outputs are Simulation / Planning Estimates built from configurable
    assumptions – they are NOT audited cost data.
    """
    params = get_params(db)
    cost_map = params["cost_per_problem"]
    ben_map = params["beneficiaries_per_problem"]

    clusters = db.scalars(
        select(ProblemCluster).where(
            ProblemCluster.status.in_(("new", "action_required", "reopened"))
        )
    ).all()
    candidates = [c for c in clusters if c.category and c.category.slug in sectors]
    # critical first, then score desc
    level_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    candidates.sort(key=lambda c: (level_rank.get(c.priority_level, 9), -c.priority_score))

    remaining = float(budget)
    addressed = []
    total_cost = 0.0
    beneficiaries = 0
    critical_reduced = 0

    for c in candidates:
        cost = float(cost_map.get(c.category.slug if c.category else "other", 50000))
        if cost > remaining:
            continue
        addressed.append(c)
        remaining -= cost
        total_cost += cost
        beneficiaries += int(ben_map.get(c.category.slug if c.category else "other", 300))
        if c.priority_level == "critical":
            critical_reduced += 1
        if remaining <= 0:
            break

    max_ben = sum(int(ben_map.get(c.category.slug if c.category else "other", 300)) for c in candidates)
    max_crit = sum(1 for c in candidates if c.priority_level == "critical")

    impact_score = 0.0
    if candidates:
        reach = beneficiaries / max_ben if max_ben else 0
        crit_share = critical_reduced / max_crit if max_crit else 0
        impact_score = round(min(100.0, (reach * 60 + crit_share * 40) * 100), 1)

    return {
        "disclaimer": "Simulation / Planning Estimate based on configurable assumptions – not audited cost data.",
        "budget_input": budget,
        "sectors_selected": sectors,
        "problems_addressed": len(addressed),
        "estimated_citizens_benefited": beneficiaries,
        "critical_problems_reduced": critical_reduced,
        "estimated_cost_used": round(total_cost, 2),
        "remaining_budget": round(max(remaining, 0), 2),
        "impact_score": impact_score,
        "selected": [
            {"code": c.code, "title": c.title, "priority": c.priority_score,
             "level": c.priority_level, "category": c.category.slug if c.category else None}
            for c in addressed[:25]
        ],
    }
