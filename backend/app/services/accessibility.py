"""Accessibility gap analysis (geospatial planning insights).

For each settlement × facility type we compute the nearest facility using the
haversine/PostGIS distance and flag gaps beyond configurable thresholds.
Results are explicitly labelled: 'AI/Data-based planning insight' – they are
NOT certified government or medical assessments.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.geo import AccessibilityGap, Facility
from app.models.system import SimulationParameter
from app.services.audit import record_audit
from app.services.geo import haversine_m

THRESHOLDS_KM = {"healthcare": 10.0, "education": 5.0, "water": 2.0, "emergency": 15.0}

# Demo settlements live in simulation_parameters so admins can edit them.
DEFAULT_SETTLEMENTS = [
    {"name": "Ward 4 – Hindpiri", "type": "ward", "lat": 23.3620, "lng": 85.3320, "population": 14500},
    {"name": "Village Chota Nagri", "type": "village", "lat": 23.2880, "lng": 85.2100, "population": 6200},
    {"name": "Ward 12 – Doranda", "type": "ward", "lat": 23.3550, "lng": 85.3570, "population": 22000},
    {"name": "Village Bariatu East", "type": "village", "lat": 23.4200, "lng": 85.2900, "population": 4800},
]


def _settlements(db: Session) -> list[dict]:
    row = db.get(SimulationParameter, "accessibility.settlements")
    if row and isinstance(row.value_json, list):
        return row.value_json
    return DEFAULT_SETTLEMENTS


def compute_gaps(db: Session, actor_id: str | None = None) -> int:
    settlements = _settlements(db)
    facilities = db.scalars(select(Facility)).all()
    created = 0

    for st in settlements:
        for ftype, threshold_km in THRESHOLDS_KM.items():
            nearest, dist_m = None, None
            for f in facilities:
                if f.facility_type != ftype:
                    continue
                d = haversine_m(st["lat"], st["lng"], f.latitude, f.longitude)
                if dist_m is None or d < dist_m:
                    nearest, dist_m = f, d

            dist_km = round(dist_m / 1000.0, 2) if dist_m is not None else None
            over = max(0.0, (dist_km or threshold_km) - threshold_km)
            gap_score = round(min(100.0, (over / threshold_km) * 70 + min(30.0, st["population"] / 1000.0)), 1)
            severity = "severe" if gap_score >= 60 else ("moderate" if gap_score >= 30 else "none")
            insight = (
                f"{st['name']} is approximately {dist_km} km from the nearest {ftype} "
                f"facility ({nearest.name if nearest else 'none found'}); population ~{st['population']}."
            ) + (" Potential Accessibility Gap" if severity != "none" else "")
            insight += " [AI/Data-based planning insight]"

            db.add(
                AccessibilityGap(
                    area_label=st["name"], area_type=st["type"],
                    latitude=st["lat"], longitude=st["lng"],
                    facility_type=ftype, population_est=st["population"],
                    nearest_facility_id=nearest.id if nearest else None,
                    nearest_facility_name=nearest.name if nearest else None,
                    nearest_distance_km=dist_km,
                    gap_score=gap_score, severity_label=severity,
                    insight_text=insight,
                    parameters_snapshot={"thresholds_km": THRESHOLDS_KM},
                )
            )
            created += 1

    db.commit()
    record_audit(actor_id, "admin", "accessibility.gaps_computed", "system", "accessibility_gaps",
                 after={"rows": created}, reason="scheduled/admin recompute")
    return created
