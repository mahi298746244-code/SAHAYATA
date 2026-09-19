"""API v1 router aggregation."""
from fastapi import APIRouter

from app.api.v1 import (
    accessibility,
    actions,
    admin_users,
    analytics,
    auth,
    catalog,
    health,
    map,
    media,
    notifications,
    priorities,
    problems,
    reports,
    search,
    simulator,
    verifications,
)

api_router = APIRouter(prefix="/api/v1")
for r in (
    auth.router, reports.router, problems.router, actions.router,
    verifications.router, map.router, priorities.router, analytics.router,
    simulator.router, accessibility.router, notifications.router,
    catalog.router, search.router, admin_users.router, media.router,
    health.router,
):
    api_router.include_router(r)
