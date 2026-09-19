"""In-app notifications for the signed-in user."""
from datetime import datetime

from fastapi import APIRouter, Query, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbDep
from app.db.base import utcnow
from app.models.system import Notification
from app.schemas.misc import NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(
    db: DbDep,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    unread_only: bool = False,
):
    stmt = select(Notification).where(Notification.recipient_id == str(user.id))
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    from sqlalchemy import func as f

    total = db.scalar(select(f.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(Notification.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    unread = db.scalar(
        select(f.count()).select_from(
            select(Notification.id).where(
                Notification.recipient_id == str(user.id), Notification.read_at.is_(None)
            ).subquery()
        )
    ) or 0
    return {
        "items": [NotificationOut.model_validate(n).model_dump(mode="json") for n in rows],
        "total": total, "unread": unread, "page": page, "page_size": page_size,
    }


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_read(notification_id: str, db: DbDep, user: CurrentUser):
    n = db.get(Notification, notification_id)
    if n and n.recipient_id == str(user.id) and n.read_at is None:
        n.read_at = utcnow()
        db.commit()


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_read(db: DbDep, user: CurrentUser):
    for n in db.scalars(
        select(Notification).where(Notification.recipient_id == str(user.id), Notification.read_at.is_(None))
    ).all():
        n.read_at = utcnow()
    db.commit()
