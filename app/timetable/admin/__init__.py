"""Initialization for the admin package."""

from .filters import (
    SectionBySemesterFilter,
    SectionFacultyFilterAc,
    SemesterFilterAC,
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
    # Admin
    "AcademicYearAdmin",
    "SecSessionAdmin",
    "SectionAdmin",
    "SemesterAdmin",
    "TermAdmin",
    # Resource
    "AcademicYearResource",
    "SecSessionResource",
    "ScheduleResource",
    "SectionResource",
    "SemesterResource",
    # Inline
    "SectionInline",
    "SemesterInline",
    # Filters
    "SectionBySemesterAutocom",
    "SectionBySemesterFilter",
    "SectionFacultyFilterAc",
    "SemesterFilterAC",
]
