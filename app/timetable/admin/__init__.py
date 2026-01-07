"""Initialization for the admin package."""

from .core_registers import AcademicYearAdmin, SemesterAdmin, TermAdmin
from .core_resources import AcademicYearResource, SemesterResource
from .filters import (
    SectionBySemesterFilter,
    SectionFacultyFilterAc,
    SemesterFilterAC,
)
from .inlines import SectionInline, SemesterInline
from .section_registers import SectionAdmin
from .section_resources import SectionResource
from .session_resources import ScheduleResource, SecSessionResource
from .session_registers import SecSessionAdmin
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
