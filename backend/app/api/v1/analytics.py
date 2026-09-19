"""Analytics endpoints – all values computed live from the database."""
from fastapi import APIRouter, Query

from app.api.deps import AuthorityUser, CurrentUser, DbDep
from app.services.analytics import (
    by_category,
    department_performance,
    full_analytics,
    overview,
    resolution_time,
    trends,
    verification_stats,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview")
def analytics_overview(db: DbDep, user: CurrentUser):
    return overview(db)


@router.get("/full")
def analytics_full(db: DbDep, user: AuthorityUser):
    return full_analytics(db)


@router.get("/trends")
def analytics_trends(db: DbDep, user: AuthorityUser, days: int = Query(14, ge=1, le=180)):
    return trends(db, days)


@router.get("/by-category")
def analytics_by_category(db: DbDep, user: AuthorityUser):
    return by_category(db)


@router.get("/departments")
def analytics_departments(db: DbDep, user: AuthorityUser):
    return department_performance(db)


@router.get("/verification")
def analytics_verification(db: DbDep, user: AuthorityUser):
    return verification_stats(db)


@router.get("/resolution-time")
def analytics_resolution(db: DbDep, user: AuthorityUser):
    return resolution_time(db)
