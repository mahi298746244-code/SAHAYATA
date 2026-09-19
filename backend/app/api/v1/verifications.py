"""Citizen verification of resolutions – the accountability core."""
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbDep, role_name
from app.db.base import utcnow
from app.models.civic import ClusterReport, ProblemCluster, Report
from app.models.system import AuditLog
from app.models.user import Role, User
from app.models.work import Action, Verification
from app.schemas.civic import VerificationCreate, VerificationOut
from app.services.notify import notify

router = APIRouter(prefix="/verifications", tags=["verifications"])


@router.post("", response_model=VerificationOut, status_code=status.HTTP_201_CREATED)
def submit_verification(payload: VerificationCreate, db: DbDep, user: CurrentUser):
    cluster = db.scalar(select(ProblemCluster).where(ProblemCluster.code == payload.problem_id))
    if not cluster:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Problem not found")
    if cluster.status != "verification_pending":
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"problem is not awaiting verification (status={cluster.status})")

    role = role_name(user)
    if role == "citizen":
        member = db.scalar(
            select(ClusterReport).where(
                ClusterReport.cluster_id == cluster.id,
                ClusterReport.report_id.in_(select(Report.id).where(Report.citizen_id == str(user.id))),
            )
        )
        if not member:
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                "only citizens who reported this problem can verify it")

    action = db.scalar(select(Action).where(Action.cluster_id == cluster.id).order_by(Action.created_at.desc()))

    v = Verification(
        cluster_id=cluster.id,
        action_id=action.id if action else None,
        citizen_id=str(user.id),
        verdict=payload.verdict,
        comment=payload.comment[:1000],
    )
    db.add(v)

    before = cluster.status
    if payload.verdict == "yes":
        cluster.status = "verified"
        cluster.resolved_at = utcnow()
        for r in db.scalars(select(Report).where(Report.cluster_id == cluster.id)).all():
            r.status = "verified"
        if action:
            action.status = "closed"
            action.closed_at = utcnow()
    elif payload.verdict == "no":
        cluster.status = "action_required"
        cluster.resolved_at = None
        for r in db.scalars(select(Report).where(Report.cluster_id == cluster.id)).all():
            r.status = "reopened"
        if action:
            action.status = "reopened"
    # partial → stays verification_pending; recorded in history for the authority

    db.commit()
    db.refresh(v)

    db.add(AuditLog(
        actor_id=str(user.id), actor_role=role,
        action="verification.submit", entity_type="problem_cluster", entity_id=cluster.code,
        before={"status": before}, after={"status": cluster.status, "verdict": payload.verdict},
        reason=payload.comment or None,
    ))
    db.commit()

    # Notify authorities about the outcome
    auth_role_ids = [
        r.id for r in db.scalars(select(Role).where(Role.name.in_(("authority", "admin")))).all()
    ]
    users = db.scalars(select(User).where(User.role_id.in_(auth_role_ids), User.is_active)).all()
    if payload.verdict == "no":
        notify({u.id for u in users}, "verification_failed",
               f"Verification FAILED for {cluster.code}",
               f"A citizen rejected the resolution of '{cluster.title}'. Problem returned to Action Required.",
               {"problem_code": cluster.code})
    elif payload.verdict == "yes":
        notify({u.id for u in users}, "verification_passed",
               f"{cluster.code} verified by citizen",
               f"'{cluster.title}' was confirmed resolved and moved to Verified.",
               {"problem_code": cluster.code})

    return VerificationOut.model_validate(v)


@router.get("/problem/{code}", response_model=list[VerificationOut])
def verification_history(code: str, db: DbDep, user: CurrentUser):
    cluster = db.scalar(select(ProblemCluster).where(ProblemCluster.code == code))
    if not cluster:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Problem not found")
    rows = db.scalars(
        select(Verification).where(Verification.cluster_id == cluster.id).order_by(Verification.created_at)
    ).all()
    return [VerificationOut.model_validate(r) for r in rows]
