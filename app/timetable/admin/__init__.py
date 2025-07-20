"""Initialization for the admin package."""

from .filters import (
    SectionBySemesterFilter,
    SemesterFilter,
    SectionSemesterFilterAc,
    GradeSemesterFilterAc,
)
from .inlines import SectionInline, SemesterInline
from .registers.core import AcademicYearAdmin, SemesterAdmin
from .registers.section import SectionAdmin
from .registers.session import SecSessionAdmin
from .resources.core import AcademicYearResource, SemesterResource
from .resources.section import SectionResource
from .views import SectionBySemesterAutocomplete

__all__ = [
    "AcademicYearAdmin",
    "AcademicYearResource",
    "SectionAdmin",
    "SectionBySemesterAutocom",
    "SectionBySemesterFilter",
    "SectionSemesterFilterAc",
    "GradeSemesterFilterAc",
    "SemesterFilter",
    "SectionInline",
    "SectionResource",
    "SemesterAdmin",
    "SectionSemesterFilterAc",
    "SemesterInline",
    "SemesterResource",
    "SecSessionAdmin",
]
