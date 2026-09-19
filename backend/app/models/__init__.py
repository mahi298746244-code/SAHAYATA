"""Import all models so Base.metadata and Alembic see the full schema."""
from app.models.user import RefreshToken, Role, User
from app.models.catalog import Category, Department
from app.models.civic import ClusterReport, ProblemCluster, Report, ReportMedia
from app.models.work import Action, ActionResource, EvidenceMedia, ResolutionEvidence, Verification
from app.models.geo import AccessibilityGap, Facility
from app.models.system import AiPrediction, AuditLog, Notification, SimulationParameter

__all__ = [
    "Role", "User", "RefreshToken",
    "Category", "Department",
    "Report", "ReportMedia", "ProblemCluster", "ClusterReport",
    "Action", "ActionResource", "ResolutionEvidence", "EvidenceMedia", "Verification",
    "Facility", "AccessibilityGap",
    "AiPrediction", "AuditLog", "Notification", "SimulationParameter",
]
