"""Report processing pipeline: classify → analyse media → cluster → notify.

Runs asynchronously (FastAPI BackgroundTasks) after a report is accepted so
the citizen is never blocked. Every stage degrades gracefully and records an
ai_predictions row on success AND failure.
"""
import hashlib

from app.ai import image_analysis, severity_rules
from app.ai import text_classifier
from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.models.civic import ProblemCluster, Report, ReportMedia
from app.models.system import AiPrediction
from app.services import clustering
from app.services.notify import notify

log = get_logger("sahayata.pipeline")

SEVERITY_BASE = {
    "roads": 2, "water": 3, "electricity": 3, "garbage": 2, "drainage": 3,
    "street_lighting": 2, "healthcare": 4, "education": 2,
    "public_safety": 4, "sanitation": 2, "public_transport": 2,
    "environment": 2, "other": 2,
}


def _slug_by_id(db, category_id):
    from app.models.catalog import Category

    if not category_id:
        return None
    cat = db.get(Category, category_id)
    return cat.slug if cat else None


def process_report(report_id: str) -> None:
    """Pipeline entry point. Must never raise."""
    db = SessionLocal()
    try:
        report = db.get(Report, report_id)
        if not report or report.deleted_at:
            return

        text = f"{report.title} {report.description or ''}"
        digest = hashlib.sha256(text.encode()).hexdigest()

        # ---------- 1. Text classification ----------
        if settings.AI_TEXT_ENABLED and text_classifier.available():
            result = text_classifier.classify(text)
            if result:
                from app.models.catalog import Category

                cat = db.query(Category).filter_by(slug=result["category_slug"]).first()
                report.ai_category_id = cat.id if cat else None
                report.ai_confidence = result["confidence"]
                report.ai_keywords = result["keywords"]
                if not report.category_id:
                    report.category_id = cat.id if cat else None
                    report.category_source = "ai"
                    report.subcategory = severity_rules.detect_subcategory(
                        result["category_slug"], text
                    )
                else:
                    report.subcategory = report.subcategory or severity_rules.detect_subcategory(
                        _slug_by_id(db, report.category_id), text
                    )
                report.ai_status = "done"
                db.add(
                    AiPrediction(
                        subject_type="report",
                        subject_id=report.id,
                        task="text_classification",
                        provider=f"local-sklearn:{result['model_name']}",
                        model_name=result["model_name"],
                        model_version=result["model_version"],
                        input_digest=digest,
                        payload={"top3": result["top3"], "keywords": result["keywords"]},
                        confidence=result["confidence"],
                        success=True,
                    )
                )
            else:
                report.ai_status = "failed"
        else:
            report.ai_status = "skipped"

        # ---------- 2. Severity / urgency rules ----------
        slug = _slug_by_id(db, report.category_id)
        report.ai_severity = severity_rules.score_severity(text, SEVERITY_BASE, slug)
        report.ai_urgency = severity_rules.score_urgency(text)

        # ---------- 3. Media analysis ----------
        for m in db.query(ReportMedia).filter(ReportMedia.report_id == report.id).all():
            if m.kind == "image" and m.processing_status == "pending":
                try:
                    data = _read_media(m.storage_key)
                    local = image_analysis.analyze_image(data)
                    external = image_analysis.external_labels(data) or {}
                    labels = {
                        **local,
                        **({"external": external} if external else {}),
                    }
                    m.width, m.height = local.get("width"), local.get("height")
                    m.phash = local.get("phash")
                    m.ai_labels = labels
                    m.processing_status = "done"
                    db.add(
                        AiPrediction(
                            subject_type="media", subject_id=m.id,
                            task="image_analysis",
                            provider=labels.get("provider", "local-rules"),
                            model_name=labels.get("provider", "local-rules"),
                            model_version="1.0.0",
                            input_digest=m.sha256,
                            payload={"quality": local.get("quality"), "labels": labels.get("external", {}).get("labels", [])},
                            confidence=(labels.get("external", {}).get("labels") or [{}])[0].get("confidence"),
                            success=True,
                        )
                    )
                except Exception as exc:  # invalid image etc.
                    m.processing_status = "failed"
                    db.add(
                        AiPrediction(
                            subject_type="media", subject_id=m.id,
                            task="image_analysis", provider="local-rules",
                            model_name="local-rules", model_version="1.0.0",
                            success=False, error=str(exc)[:500],
                        )
                    )
            elif m.kind in ("audio", "video"):
                # Audio transcripts come from browser Web Speech API; server-side
                # STT is optional (ENABLE_LOCAL_STT) and intentionally not faked.
                m.processing_status = "skipped"

        db.commit()

        # ---------- 4. Clustering + priority ----------
        db.refresh(report)
        was_new = True
        cluster, score = clustering.attach_report(db, report)

        # ---------- 5. Notifications ----------
        if report.citizen_id:
            notify(
                [report.citizen_id],
                "report_submitted",
                "Report received",
                f"Your report {report.code} – '{report.title}' has been registered."
                + (
                    " AI analysis is temporarily unavailable; it can be reviewed manually."
                    if report.ai_status != "done"
                    else ""
                ),
                {"report_code": report.code},
            )
        critical = cluster.priority_level == "critical"
        if critical or (was_new and cluster.status not in ("assigned",)):
            _alert_authorities(cluster)

        log.info(
            "pipeline complete report=%s ai=%s cluster=%s priority=%s sim=%.2f",
            report.code, report.ai_status, cluster.code,
            cluster.priority_score, score,
        )
    except Exception:
        db.rollback()
        try:
            rep = db.get(Report, report_id)
            if rep:
                rep.ai_status = "failed"
                db.commit()
        except Exception:
            pass
        log.exception("pipeline failed for report %s", report_id)
    finally:
        db.close()


def _read_media(storage_key: str) -> bytes:
    from app.services.storage import get_storage

    with get_storage().open(storage_key) as fh:
        return fh.read()


def _alert_authorities(cluster: ProblemCluster) -> None:
    from sqlalchemy import select

    from app.models.user import Role, User

    with SessionLocal() as db:
        role_ids = [
            r.id for r in db.scalars(select(Role).where(Role.name.in_(("authority", "admin")))).all()
        ]
        users = db.scalars(select(User).where(User.role_id.in_(role_ids), User.is_active)).all()
        notify(
            {u.id for u in users},
            "critical_issue",
            f"Critical problem reported: {cluster.title}",
            f"{cluster.code} scored {cluster.priority_score:.0f}/100 "
            f"({cluster.priority_level}). Immediate review recommended.",
            {"problem_code": cluster.code},
        )
