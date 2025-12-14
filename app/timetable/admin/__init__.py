"""Initialization for the admin package."""

from .filters import (
    GradeSemesterFilterAc,
    SectionBySemesterFilter,
    SectionSemesterFilterAc,
    SemesterFilter,
)
from .inlines import SectionInline, SemesterInline
from .registers.core import AcademicYearAdmin, SemesterAdmin, TermAdmin
from .registers.section import SectionAdmin
from .registers.session import SecSessionAdmin
from .resources.core import AcademicYearResource, SemesterResource
from .resources.section import SectionResource
from .resources.session import ScheduleResource, SecSessionResource
from .views import SectionBySemesterAutocomplete

__all__ = [
    "AcademicYearAdmin",
    "AcademicYearResource",
    "GradeSemesterFilterAc",
    "ScheduleResource",
    "SecSessionAdmin",
    "SecSessionResource",
    "SectionAdmin",
    "SectionBySemesterAutocom",
    "SectionBySemesterFilter",
    "SectionInline",
    "SectionResource",
    "SectionSemesterFilterAc",
    "SectionSemesterFilterAc",
    "SemesterAdmin",
    "SemesterFilter",
    "SemesterInline",
    "SemesterResource",
    "TermAdmin",
]
