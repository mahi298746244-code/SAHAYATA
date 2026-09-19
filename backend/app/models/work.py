"""Work management: actions, resources, resolution evidence and verifications."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow


class Action(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "actions"

    code: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    cluster_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("problem_clusters.id"), index=True, nullable=False
    )
    department_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("departments.id"), nullable=False)
    officer_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("users.id"), index=True)
    team_name: Mapped[str | None] = mapped_column(String(150))
    resources_needed: Mapped[str | None] = mapped_column(String(1000))
    estimated_cost: Mapped[float | None] = mapped_column(Float)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    priority_level_snapshot: Mapped[str] = mapped_column(String(12), default="medium")
    priority_score_snapshot: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(24), default="assigned", index=True, nullable=False)
    # assigned|in_progress|completed|verification_pending|reopened|closed|cancelled

    notes: Mapped[str | None] = mapped_column(String(2000))
    created_by_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("users.id"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    cluster = relationship("ProblemCluster", lazy="joined")
    department = relationship("Department", lazy="joined")
    officer = relationship("User", foreign_keys=[officer_id], lazy="joined")


class ActionResource(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "action_resources"

    action_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("actions.id"), index=True)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_cost: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(String(300))


class ResolutionEvidence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "resolution_evidence"

    action_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("actions.id"), index=True)
    note: Mapped[str] = mapped_column(String(2000), default="")
    completion_details: Mapped[str | None] = mapped_column(String(2000))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    submitted_by_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("users.id"))

    media = relationship("ReportMedia", secondary="evidence_media", lazy="select")


class EvidenceMedia(Base):
    __tablename__ = "evidence_media"
    __table_args__ = (UniqueConstraint("evidence_id", "media_id", name="uq_evidence_media"),)

    evidence_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("resolution_evidence.id"), primary_key=True
    )
    media_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("report_media.id"), primary_key=True)


class Verification(Base):
    __tablename__ = "verifications"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    cluster_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("problem_clusters.id"), index=True, nullable=False
    )
    action_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("actions.id"), index=True)
    citizen_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("users.id"), index=True)
    verdict: Mapped[str] = mapped_column(String(12), nullable=False)  # yes|no|partial
    comment: Mapped[str] = mapped_column(String(1000), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
