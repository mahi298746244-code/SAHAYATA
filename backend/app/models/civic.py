"""Core civic models: reports, media, problem clusters and links."""
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow


class Report(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reports"
    __table_args__ = (
        Index("ix_reports_latlng", "latitude", "longitude"),
        Index("ix_reports_created", "created_at"),
    )

    code: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    citizen_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(4000), default="", nullable=False)

    # Final category (manual or AI-accepted); AI suggestion kept in ai fields.
    category_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("categories.id"), index=True)
    subcategory: Mapped[str | None] = mapped_column(String(120))
    category_source: Mapped[str] = mapped_column(String(20), default="user")  # user|ai|admin
    ai_category_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("categories.id"))
    ai_confidence: Mapped[float | None] = mapped_column(Float)
    ai_severity: Mapped[int | None] = mapped_column(Integer)  # 1..5
    ai_urgency: Mapped[int | None] = mapped_column(Integer)  # 1..5
    ai_keywords: Mapped[list | None] = mapped_column(JSON)
    ai_status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|done|failed|skipped
    language: Mapped[str] = mapped_column(String(8), default="en")

    status: Mapped[str] = mapped_column(String(32), default="reported", index=True, nullable=False)
    # reported|under_review|clustered|action_assigned|in_progress|resolution_submitted|
    # verification_pending|verified|closed|reopened|rejected

    address_text: Mapped[str | None] = mapped_column(String(300))
    landmark: Mapped[str | None] = mapped_column(String(200))
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    location_source: Mapped[str] = mapped_column(String(16), default="map")  # gps|map|address
    ward: Mapped[str | None] = mapped_column(String(120))
    contact_phone: Mapped[str | None] = mapped_column(String(20))
    additional_notes: Mapped[str | None] = mapped_column(String(1000))

    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    cluster_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("problem_clusters.id"), index=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    citizen = relationship("User", lazy="joined")
    category = relationship("Category", foreign_keys=[category_id], lazy="joined")
    ai_category = relationship("Category", foreign_keys=[ai_category_id], lazy="joined")
    media = relationship("ReportMedia", back_populates="report", lazy="select")


class ReportMedia(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "report_media"

    report_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("reports.id"), index=True)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)  # image|video|audio
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    duration_s: Mapped[float | None] = mapped_column(Float)
    sha256: Mapped[str | None] = mapped_column(String(64))
    phash: Mapped[str | None] = mapped_column(String(32))  # perceptual hash for images
    processing_status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|done|failed|skipped
    ai_labels: Mapped[dict | None] = mapped_column(JSON)
    created_by_role: Mapped[str] = mapped_column(String(20), default="citizen")  # citizen|authority
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    report = relationship("Report", back_populates="media")


class ProblemCluster(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "problem_clusters"
    __table_args__ = (Index("ix_clusters_latlng", "latitude", "longitude"),)

    code: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("categories.id"), index=True)
    subcategory: Mapped[str | None] = mapped_column(String(120))
    representative_report_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("reports.id"))

    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    radius_m: Mapped[int] = mapped_column(Integer, default=150)
    address_text: Mapped[str | None] = mapped_column(String(300))
    ward: Mapped[str | None] = mapped_column(String(120))

    status: Mapped[str] = mapped_column(String(32), default="new", index=True, nullable=False)
    # new|action_required|assigned|in_progress|verification_pending|reopened|verified|closed

    severity: Mapped[int] = mapped_column(Integer, default=2)  # 1..5
    urgency: Mapped[int] = mapped_column(Integer, default=2)
    priority_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    priority_level: Mapped[str] = mapped_column(String(12), default="low", index=True)  # low|medium|high|critical
    priority_components: Mapped[dict | None] = mapped_column(JSON)
    affected_population_est: Mapped[int] = mapped_column(Integer, default=0)

    report_count: Mapped[int] = mapped_column(Integer, default=0)
    first_reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_department_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("departments.id"))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    category = relationship("Category", lazy="joined")
    assigned_department = relationship("Department", lazy="joined")


class ClusterReport(Base):
    __tablename__ = "cluster_reports"
    __table_args__ = (UniqueConstraint("cluster_id", "report_id", name="uq_cluster_report"),)

    cluster_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("problem_clusters.id"), primary_key=True
    )
    report_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("reports.id"), primary_key=True)
    similarity: Mapped[float] = mapped_column(Float, default=1.0)
    distance_m: Mapped[float] = mapped_column(Float, default=0.0)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
