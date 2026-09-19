"""Schemas for reports, problems, actions and verifications."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MediaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str
    mime_type: str | None
    size_bytes: int
    processing_status: str
    ai_labels: dict | None
    created_at: datetime


class ReportCreate(BaseModel):
    title: str = Field(min_length=5, max_length=200)
    description: str = Field(default="", max_length=4000)
    category_id: str | None = None  # optional; AI suggests when omitted
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    address_text: str | None = Field(default=None, max_length=300)
    landmark: str | None = Field(default=None, max_length=200)
    ward: str | None = Field(default=None, max_length=120)
    location_source: str = Field(default="map", pattern="^(gps|map|address)$")
    contact_phone: str | None = Field(default=None, max_length=20)
    additional_notes: str | None = Field(default=None, max_length=1000)
    language: str = Field(default="en", max_length=8)


class ReportUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=5, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    category_id: str | None = None
    address_text: str | None = Field(default=None, max_length=300)
    landmark: str | None = Field(default=None, max_length=200)
    additional_notes: str | None = Field(default=None, max_length=1000)
    status: str | None = None  # admin corrections / citizen withdraw handled in router


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    title: str
    description: str
    status: str
    category_id: str | None
    category_name: str | None = None
    subcategory: str | None
    category_source: str
    ai_confidence: float | None
    ai_severity: int | None
    ai_urgency: int | None
    ai_keywords: list | None
    ai_status: str
    latitude: float
    longitude: float
    address_text: str | None
    landmark: str | None
    ward: str | None
    cluster_code: str | None = None
    is_public: bool
    is_demo: bool
    created_at: datetime
    updated_at: datetime


class ReportDetail(ReportOut):
    media: list[MediaOut] = []
    citizen_name: str | None = None
    contact_phone: str | None = None


class ProblemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    title: str
    status: str
    subcategory: str | None
    latitude: float
    longitude: float
    address_text: str | None
    ward: str | None
    severity: int
    urgency: int
    priority_score: float
    priority_level: str
    affected_population_est: int
    report_count: int
    assigned_department_id: str | None = None
    assigned_department_name: str | None = None
    first_reported_at: datetime
    last_reported_at: datetime
    is_demo: bool


class PriorityComponent(BaseModel):
    value: float
    weight: float
    contribution: float
    note: str


class ProblemDetail(ProblemOut):
    category_slug: str | None = None
    category_name: str | None = None
    priority_components: dict | None = None
    reports: list["ReportBrief"] = []
    actions: list["ActionOut"] = []


class MediaBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str
    mime_type: str | None = None


class ReportBrief(ReportOut):
    media: list[MediaBrief] = []


class ActionCreate(BaseModel):
    problem_id: str  # cluster code or id
    department_id: str
    officer_id: str | None = None
    team_name: str | None = Field(default=None, max_length=150)
    resources_needed: str | None = Field(default=None, max_length=1000)
    estimated_cost: float | None = Field(default=None, ge=0)
    deadline: datetime | None = None
    notes: str | None = Field(default=None, max_length=2000)


class ActionStatusUpdate(BaseModel):
    status: str
    notes: str | None = Field(default=None, max_length=2000)


class ActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    cluster_id: str
    department_id: str
    department_name: str | None = None
    officer_id: str | None
    officer_name: str | None = None
    team_name: str | None
    resources_needed: str | None
    estimated_cost: float | None
    deadline: datetime | None
    priority_level_snapshot: str
    priority_score_snapshot: float
    status: str
    notes: str | None
    started_at: datetime | None
    completed_at: datetime | None
    closed_at: datetime | None
    created_at: datetime


class EvidenceCreate(BaseModel):
    note: str = Field(max_length=2000, default="")
    completion_details: str | None = Field(default=None, max_length=2000)
    latitude: float | None = None
    longitude: float | None = None


class VerificationCreate(BaseModel):
    problem_id: str
    verdict: str = Field(pattern="^(yes|no|partial)$")
    comment: str = Field(default="", max_length=1000)


class VerificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    cluster_id: str
    action_id: str | None
    verdict: str
    comment: str
    created_at: datetime


ActionOut.model_rebuild()
ProblemDetail.model_rebuild()
