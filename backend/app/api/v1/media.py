"""Authenticated media streaming with authorization checks."""
import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.api.deps import DbDep, get_optional_user, role_name
from app.models.civic import ClusterReport, Report, ReportMedia
from app.models.work import Action, EvidenceMedia, ResolutionEvidence
from app.models.user import User
from app.services.storage import StorageError, get_storage

router = APIRouter(prefix="/media", tags=["media"])


def _can_view(user: User | None, db, media: ReportMedia) -> bool:
    if user is None or user.deleted_at or not user.is_active:
        return False
    role = role_name(user)
    if role in ("authority", "admin"):
        return True

    # Citizen report media
    if media.report_id is not None:
        report = media.report
        return str(report.citizen_id) == str(user.id) or bool(report.is_public)

    # Resolution evidence media: staff handled above; allow reporters of the cluster
    link = db.scalar(select(EvidenceMedia).where(EvidenceMedia.media_id == media.id))
    if not link:
        return False
    evidence = db.get(ResolutionEvidence, link.evidence_id)
    if not evidence:
        return False
    action = db.get(Action, evidence.action_id)
    if not action:
        return False
    member = db.scalar(
        select(ClusterReport).where(
            ClusterReport.cluster_id == action.cluster_id,
            ClusterReport.report_id.in_(select(Report.id).where(Report.citizen_id == str(user.id))),
        )
    )
    return member is not None


@router.get("/{media_id}")
def stream_media(media_id: str, db: DbDep, user: User | None = Depends(get_optional_user)):
    media = db.get(ReportMedia, media_id)
    if not media:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Media not found")

    if not _can_view(user, db, media):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to view this media")

    try:
        fh = get_storage().open(media.storage_key)
    except StorageError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File missing") from None

    mime = media.mime_type or mimetypes.guess_type(Path(media.storage_key).name)[0] or "application/octet-stream"
    return StreamingResponse(fh, media_type=mime)
