"""Dialect-aware geospatial helpers.

On PostgreSQL the initial migration adds a PostGIS generated column
`geom geography(Point,4326)` plus GiST indexes; spatial queries use PostGIS
functions (ST_DistanceSphere) against it. On other dialects (sqlite dev/test)
we prefilter with a bounding box and refine with a Python haversine so the
application behaves identically everywhere.
"""
import math

from sqlalchemy import func, literal, select
from sqlalchemy.orm import Session

from app.core.config import settings


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in metres."""
    r = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def distance_expr(model, lat: float, lng: float):
    """SQL expression returning distance in metres from point to each row."""
    if settings.is_postgres:
        return func.ST_DistanceSphere(
            func.ST_SetSRID(func.ST_MakePoint(literal(float(lng)), literal(float(lat))), 4326),
            func.ST_SetSRID(func.ST_MakePoint(model.longitude, model.latitude), 4326),
        )
    return None  # sqlite path refines in Python


def _bbox(lat: float, lng: float, radius_m: float) -> tuple[float, float, float, float]:
    dlat = radius_m / 111_320.0
    dlng = radius_m / max(1.0, 111_320.0 * math.cos(math.radians(lat)))
    return lat - dlat, lat + dlat, lng - dlng, lng + dlng


def find_nearby(
    session: Session,
    model,
    lat: float,
    lng: float,
    radius_m: float,
    filters: dict | None = None,
) -> list[tuple[object, float]]:
    """Return [(row, distance_m)] for rows within radius, sorted by distance."""
    min_lat, max_lat, min_lng, max_lng = _bbox(lat, lng, radius_m)
    stmt = select(model).where(
        model.latitude.between(min_lat, max_lat),
        model.longitude.between(min_lng, max_lng),
    )
    for col, value in (filters or {}).items():
        stmt = stmt.where(getattr(model, col) == value)

    rows = session.execute(stmt).scalars().all()

    if settings.is_postgres:
        dist = distance_expr(model, lat, lng)
        stmt = stmt.add_columns(dist).where(dist <= radius_m).order_by(dist)
        result = session.execute(stmt).all()
        out: list[tuple[object, float]] = []
        seen = set()
        for row_obj, d in result:
            if row_obj.id in seen:
                continue
            seen.add(row_obj.id)
            out.append((row_obj, float(d)))
        return out

    scored = [(r, haversine_m(lat, lng, r.latitude, r.longitude)) for r in rows]
    return sorted(((r, d) for r, d in scored if d <= radius_m), key=lambda x: x[1])
