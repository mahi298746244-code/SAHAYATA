"""In-app notification service.

Architecture note: this is the single place notifications are created, so
email / SMS / WhatsApp channels can be added later by extending the `send`
fan-out without touching business logic.
"""
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.models.system import Notification

log = get_logger("sahayata.notify")

# recipient user ids -> list of (type, title, body, data)
BATCH: dict[str, list[tuple]] = {}


def notify(
    recipient_ids: list[str] | set[str],
    type_: str,
    title: str,
    body: str,
    data: dict | None = None,
) -> None:
    """Create in-app notifications. Runs in its own session; never raises."""
    recipients = {r for r in recipient_ids if r}
    if not recipients:
        return
    try:
        with SessionLocal() as db:
            for rid in recipients:
                db.add(
                    Notification(
                        recipient_id=rid,
                        type=type_,
                        title=title[:200],
                        body=body[:1000],
                        data=data or {},
                        channel="in_app",
                    )
                )
            db.commit()
    except Exception:
        log.exception("notification write failed type=%s", type_)
