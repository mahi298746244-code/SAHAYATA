"""System models: notifications, audit log, simulation parameters, AI predictions."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    recipient_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # report_submitted|clustered|status_changed|...
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(String(1000))
    data: Mapped[dict | None] = mapped_column(JSON)  # deep-link payload e.g. {"problem_code": "PRB-..."}
    channel: Mapped[str] = mapped_column(String(16), default="in_app")
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    actor_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("users.id"), index=True)
    actor_role: Mapped[str | None] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. problem.priority_override
    entity_type: Mapped[str] = mapped_column(String(50), index=True)
    entity_id: Mapped[str] = mapped_column(String(64), index=True)
    before: Mapped[dict | None] = mapped_column(JSON)
    after: Mapped[dict | None] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(String(500))
    ip: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SimulationParameter(TimestampMixin, Base):
    """Configurable system parameters: priority weights, thresholds, simulator assumptions."""

    __tablename__ = "simulation_parameters"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value_json: Mapped[dict | list] = mapped_column(JSON, nullable=False)
    description: Mapped[str] = mapped_column(String(500), default="")
    updated_by_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("users.id"))


class AiPrediction(Base):
    """Immutable record of every AI inference attempt (success or failure)."""

    __tablename__ = "ai_predictions"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    subject_type: Mapped[str] = mapped_column(String(16), index=True)  # report|media|cluster
    subject_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), index=True)
    task: Mapped[str] = mapped_column(String(40))  # text_classification|image_analysis|stt_transcribe|dedup_match
    provider: Mapped[str] = mapped_column(String(50))  # local-sklearn|local-rules|openai|browser-webspeech
    model_name: Mapped[str] = mapped_column(String(100))
    model_version: Mapped[str] = mapped_column(String(50))
    input_digest: Mapped[str | None] = mapped_column(String(64))
    payload: Mapped[dict | None] = mapped_column(JSON)
    confidence: Mapped[float | None] = mapped_column(Float)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
