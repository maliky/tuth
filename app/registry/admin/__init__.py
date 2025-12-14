"""Initialization for the registry admin package."""

from app.registry.admin.resources import GradeResource
from app.registry.admin.resources_legacy import LegacyGradeSheetResource, LegacyRegistrationResource
from .core import GradeAdmin
from .filters import GradeSectionFilter
__all__ = [
    "DocumentStudentInline",
    "GradeAdmin",
    "GradeInline",
    "GradeResource",
    "GradeSectionFilter",
    "LegacyGradeSheetResource",
    "LegacyRegistrationResource",
]
