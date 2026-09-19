"""Health & system status endpoint."""
from fastapi import APIRouter
from sqlalchemy import select, text

from app.api.deps import DbDep
from app.core.config import settings

router = APIRouter(tags=["system"])


@router.get("/health")
def health(db: DbDep):
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    ai_status = "disabled"
    if settings.AI_TEXT_ENABLED:
        from app.ai import text_classifier

        ai_status = "ready" if text_classifier.available() else "unavailable"

    return {
        "status": "ok" if db_ok else "degraded",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "database": "postgres+postgis" if settings.is_postgres else ("sqlite-dev" if db_ok else "down"),
        "ai_text": ai_status,
        "ai_vision": settings.AI_VISION_PROVIDER,
        "storage_driver": settings.STORAGE_DRIVER,
    }
