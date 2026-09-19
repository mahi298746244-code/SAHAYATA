"""GIS models: public facilities and accessibility gaps."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow


class Facility(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "facilities"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    facility_type: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    # healthcare|education|water|emergency
    subtype: Mapped[str | None] = mapped_column(String(100))  # PHC, school, handpump...
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    address: Mapped[str | None] = mapped_column(String(300))
    district: Mapped[str | None] = mapped_column(String(120), index=True)
    ward: Mapped[str | None] = mapped_column(String(120))
    capacity_note: Mapped[str | None] = mapped_column(String(300))
    service_level: Mapped[str] = mapped_column(String(16), default="full")  # full|limited|basic
    is_demo: Mapped[bool] = mapped_column(default=False)


class AccessibilityGap(TimestampMixin, Base):
    """Computed planning insight. Clearly labelled as AI/data-based, not official."""

    __tablename__ = "accessibility_gaps"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    area_label: Mapped[str] = mapped_column(String(200), nullable=False)  # village/ward name
    area_type: Mapped[str] = mapped_column(String(20), default="ward")  # ward|village
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    facility_type: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    population_est: Mapped[int] = mapped_column(Integer, default=0)
    nearest_facility_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("facilities.id"))
    nearest_facility_name: Mapped[str | None] = mapped_column(String(200))
    nearest_distance_km: Mapped[float | None] = mapped_column(Float)
    gap_score: Mapped[float] = mapped_column(Float, default=0.0)  # 0..100
    severity_label: Mapped[str] = mapped_column(String(12), default="none")  # none|moderate|severe
    insight_text: Mapped[str | None] = mapped_column(String(1000))  # labelled AI/Data-based planning insight
    parameters_snapshot: Mapped[dict | None] = mapped_column(JSON)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
