"""Action management: create from problem, status workflow, evidence upload."""
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select

from app.api.deps import AuthorityUser, CurrentUser, DbDep, role_name
from app.db.base import utcnow
from app.models.civic import ProblemCluster, Report
from app.models.system import AuditLog
from app.models.work import Action, ResolutionEvidence, EvidenceMedia
from app.models.catalog import Department
from app.schemas.civic import ActionCreate, ActionOut
from app.services.ids import next_code
from app.services.notify import notify
from app.services.uploads import UploadRejected, store_upload

router = APIRouter(prefix="/actions", tags=["actions"])

VALID_TRANSITIONS = {
    "assigned": {"in_progress", "cancelled"},
    "in_progress": {"completed", "cancelled"},
    "completed": {"verification_pending", "reopened"},
    "verification_pending": {"closed", "reopened"},
    "reopened": {"in_progress", "completed", "cancelled"},
}


def _action_out(a: Action) -> dict:
    d = ActionOut.model_validate(a).model_dump(mode="json")
    return d


@router.get("")
def list_actions(
    db: DbDep,
    user: AuthorityUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_: str | None = Query(None, alias="status"),
    department_id: str | None = None,
):
    stmt = select(Action)
    if status_:
        stmt = stmt.where(Action.status == status_)
    if department_id:
        stmt = stmt.where(Action.department_id == department_id)
    from sqlalchemy import func as f

    total = db.scalar(select(f.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Action.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [_action_out(a) for a in rows], "total": total, "page": page, "page_size": page_size}


@router.post("", response_model=ActionOut, status_code=status.HTTP_201_CREATED)
def create_action(payload: ActionCreate, db: DbDep, user: AuthorityUser):
    cluster = _resolve_cluster(db, payload.problem_id)
    if not cluster:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Problem not found")
    if cluster.status in ("verified", "closed"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Problem already resolved")

    dept = db.get(Department, payload.department_id)
    if not dept:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "unknown department")

    action = Action(
        code=next_code(db, "action"),
        cluster_id=cluster.id,
        department_id=payload.department_id,
        officer_id=payload.officer_id,
        team_name=payload.team_name,
        resources_needed=payload.resources_needed,
        estimated_cost=payload.estimated_cost,
        deadline=payload.deadline,
        priority_level_snapshot=cluster.priority_level,
        priority_score_snapshot=cluster.priority_score,
        status="assigned",
        notes=payload.notes,
        created_by_id=str(user.id),
    )
    cluster.status = "assigned"
    cluster.assigned_department_id = dept.id
    for r in db.scalars(select(Report).where(Report.cluster_id == cluster.id)).all():
        r.status = "action_assigned"
    db.add(action)
    db.commit()
    db.refresh(action)

    db.add(AuditLog(
        actor_id=str(user.id), actor_role=role_name(user),
        action="action.create", entity_type="action", entity_id=action.code,
        after={"cluster": cluster.code, "department": dept.name},
    ))
    db.commit()

    reporter_ids = {str(r.citizen_id) for r in db.scalars(select(Report).where(Report.cluster_id == cluster.id)).all() if r.citizen_id}
    notify(reporter_ids, "status_changed", f"Work assigned for {cluster.code}",
           f"Department {dept.name} has taken up your reported problem '{cluster.title}'.",
           {"problem_code": cluster.code})
    return _action_out(action)


@router.get("/{code}", response_model=ActionOut)
def get_action(code: str, db: DbDep, user: AuthorityUser):
    action = db.scalar(select(Action).where(Action.code == code))
    if not action:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Action not found")
    return _action_out(action)


@router.patch("/{code}", response_model=ActionOut)
def update_action_status(code: str, payload: dict, db: DbDep, user: AuthorityUser):
    action = db.scalar(select(Action).where(Action.code == code))
    if not action:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Action not found")
    new_status = payload.get("status")
    if new_status not in VALID_TRANSITIONS.get(action.status, set()):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"cannot move from '{action.status}' to '{new_status}'",
        )

    before = action.status
    action.status = new_status
    now = utcnow()
    if new_status == "in_progress":
        action.started_at = action.started_at or now
    elif new_status == "cancelled":
        pass
    elif new_status == "completed":
        # Evidence gate: require a note at minimum (photo encouraged via /evidence)
        has_evidence = db.scalar(
            select(ResolutionEvidence.id).where(ResolutionEvidence.action_id == action.id).limit(1)
        )
        if not has_evidence and not (payload.get("notes") or "").strip() and not (action.notes or "").strip():
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                "resolution evidence or completion notes required")
        action.completed_at = now
    elif new_status == "closed":
        action.closed_at = now
        action.cluster.status = "closed"
        action.cluster.resolved_at = action.cluster.resolved_at or now
    elif new_status == "reopened":
        action.cluster.status = "action_required"

    if payload.get("notes"):
        action.notes = payload["notes"]

    # mirror to member reports
    report_status_map = {
        "assigned": "action_assigned", "in_progress": "in_progress",
        "completed": "resolution_submitted", "reopened": "reopened", "closed": "closed",
    }
    if new_status in report_status_map:
        for r in db.scalars(select(Report).where(Report.cluster_id == action.cluster_id)).all():
            r.status = report_status_map[new_status]

    db.commit()
    db.add(AuditLog(
        actor_id=str(user.id), actor_role=role_name(user),
        action="action.status_change", entity_type="action", entity_id=action.code,
        before={"status": before}, after={"status": new_status}, reason=payload.get("reason"),
    ))
    db.commit()
    db.refresh(action)

    reporter_ids = {str(r.citizen_id) for r in db.scalars(select(Report).where(Report.cluster_id == action.cluster_id)).all() if r.citizen_id}
    titles = {
        "in_progress": ("Work started", "The department has started work on your reported problem."),
        "completed": ("Resolution submitted", "Work is marked complete and awaiting citizen verification."),
        "reopened": ("Problem reopened", "Verification indicated the problem persists; it is back with the department."),
        "closed": ("Case closed", "The reported problem has been verified and closed."),
    }
    if new_status in titles and reporter_ids:
        t, b = titles[new_status]
        notify(reporter_ids, "status_changed", t, b, {"problem_code": action.cluster.code})

    return _action_out(action)


@router.post("/{code}/evidence", status_code=status.HTTP_201_CREATED)
async def submit_evidence(
    code: str,
    db: DbDep,
    user: AuthorityUser,
    note: str = Form(""),
    completion_details: str | None = Form(None),
    latitude: float | None = Form(None),
    longitude: float | None = Form(None),
    images: list[UploadFile] = File(default=[]),
):
    """Upload 'after' evidence; moves the case to verification_pending."""
    action = db.scalar(select(Action).where(Action.code == code))
    if not action:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Action not found")
    if action.status not in ("completed", "in_progress", "verification_pending"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"evidence not allowed in status '{action.status}'")

    evidence = ResolutionEvidence(
        action_id=action.id,
        note=(note or "")[:2000],
        completion_details=(completion_details or "")[:2000],
        latitude=latitude,
        longitude=longitude,
        submitted_by_id=str(user.id),
    )
    db.add(evidence)
    db.flush()

    saved = 0
    for f in images[:6]:
        try:
            meta = store_upload(f.file, f.filename or "", f.content_type or "", max_kind_override="image")
        except UploadRejected as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{f.filename}: {exc}") from exc
        media = dict(meta)
        from app.models.civic import ReportMedia

        row = ReportMedia(created_by_role="authority", **media)
        db.add(row)
        db.flush()
        db.add(EvidenceMedia(evidence_id=evidence.id, media_id=row.id))
        saved += 1

    if not note.strip() and saved == 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "provide a note or at least one photo")

    action.status = "verification_pending"
    action.completed_at = action.completed_at or utcnow()
    action.cluster.status = "verification_pending"
    for r in db.scalars(select(Report).where(Report.cluster_id == action.cluster_id)).all():
        r.status = "verification_pending"
    db.commit()

    db.add(AuditLog(
        actor_id=str(user.id), actor_role=role_name(user),
        action="action.evidence_submitted", entity_type="action", entity_id=action.code,
        after={"images": saved},
    ))
    db.commit()

    reporter_ids = {str(r.citizen_id) for r in db.scalars(select(Report).where(Report.cluster_id == action.cluster_id)).all() if r.citizen_id}
    notify(reporter_ids, "verification_requested", "Was your problem solved?",
           f"The department marked {action.cluster.code} as resolved. Please verify.",
           {"problem_code": action.cluster.code, "action_code": action.code})

    return {"ok": True, "evidence_images": saved, "status": action.status}


def _resolve_cluster(db, problem_ref: str) -> ProblemCluster | None:
    c = db.scalar(select(ProblemCluster).where(ProblemCluster.code == problem_ref))
    if c:
        return c
    try:
        return db.get(ProblemCluster, problem_ref)
    except Exception:
        return None
