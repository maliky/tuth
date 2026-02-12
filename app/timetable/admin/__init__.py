"""Initialization for the admin package."""

from .core_registers import AcademicYearAdmin, SemesterAdmin, TermAdmin
from .core_resources import AcademicYearResource, SemesterResource
from .filters import (
    SectionBySemesterFlt,
    SectionFacultyFltAc,
    SemesterFltAC,
)
from .inlines import SectionIL, SemesterIL
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
    "SectionIL",
    "SemesterIL",
    # Flts
    "SectionBySemesterAutocom",
    "SectionBySemesterFlt",
    "SectionFacultyFltAc",
    "SemesterFltAC",
]
