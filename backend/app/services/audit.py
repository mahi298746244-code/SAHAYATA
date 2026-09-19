"""Audit logging helper – records who changed what, when, and why."""
from fastapi import Request

from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.models.system import AuditLog

log = get_logger("sahayata.audit")


def record_audit(
    actor_id: str | None,
    actor_role: str | None,
    action: str,
    entity_type: str,
    entity_id: str,
    before: dict | None = None,
    after: dict | None = None,
    reason: str | None = None,
    ip: str | None = None,
) -> None:
    """Writes an audit row in its own session so it survives caller rollbacks."""
    try:
        with SessionLocal() as db:
            db.add(
                AuditLog(
                    actor_id=actor_id,
                    actor_role=actor_role,
                    action=action,
                    entity_type=entity_type,
                    entity_id=str(entity_id),
                    before=before,
                    after=after,
                    reason=(reason or "")[:500] or None,
                    ip=ip,
                )
            )
            db.commit()
    except Exception:
        # Audit failures must never break the main flow, but must be visible.
        log.exception("audit log write failed action=%s entity=%s", action, entity_id)


def client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None
