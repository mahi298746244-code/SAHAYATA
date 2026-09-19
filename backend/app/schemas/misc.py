"""Schemas for catalog, facilities, simulator and notifications."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CategoryIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    slug: str = Field(min_length=2, max_length=100, pattern="^[a-z0-9_-]+$")
    icon: str = Field(default="circle", max_length=50)
    color: str = Field(default="#2563eb", max_length=9)
    keywords: list[str] | None = None
    parent_id: str | None = None
    department_id: str | None = None
    display_order: int = 0
    is_active: bool = True


class CategoryOut(CategoryIn):
    model_config = ConfigDict(from_attributes=True)

    id: str


class DepartmentIn(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    slug: str = Field(min_length=2, max_length=150, pattern="^[a-z0-9_-]+$")
    description: str = ""
    contact_email: str | None = None


class DepartmentOut(DepartmentIn):
    model_config = ConfigDict(from_attributes=True)

    id: str


class FacilityIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    facility_type: str = Field(pattern="^(healthcare|education|water|emergency)$")
    subtype: str | None = Field(default=None, max_length=100)
    latitude: float
    longitude: float
    address: str | None = Field(default=None, max_length=300)
    district: str | None = Field(default=None, max_length=120)
    ward: str | None = Field(default=None, max_length=120)
    capacity_note: str | None = Field(default=None, max_length=300)
    service_level: str = Field(default="full", pattern="^(full|limited|basic)$")


class FacilityOut(FacilityIn):
    model_config = ConfigDict(from_attributes=True)

    id: str
    is_demo: bool


class GapOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    area_label: str
    area_type: str
    latitude: float
    longitude: float
    facility_type: str
    population_est: int
    nearest_distance_km: float | None
    nearest_facility_name: str | None
    gap_score: float
    severity_label: str
    insight_text: str | None
    computed_at: datetime


class SimulatorRun(BaseModel):
    budget: float = Field(gt=0, le=10_000_000_000)
    sectors: list[str] = Field(min_length=1)


class SimulatorParams(BaseModel):
    cost_per_problem: dict[str, Any]
    beneficiaries_per_problem: dict[str, Any]


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    type: str
    title: str
    body: str
    data: dict | None
    read_at: datetime | None
    created_at: datetime


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    actor_id: str | None
    actor_role: str | None
    action: str
    entity_type: str
    entity_id: str
    before: dict | None
    after: dict | None
    reason: str | None
    created_at: datetime


class MapPoint(BaseModel):
    id: str
    code: str
    type: str  # problem|report|facility|gap
    lat: float
    lng: float
    title: str
    status: str | None = None
    priority_level: str | None = None
    category: str | None = None
    report_count: int | None = None
    extra: dict | None = None


class SearchResults(BaseModel):
    reports: list[dict]
    problems: list[dict]
    total: int
