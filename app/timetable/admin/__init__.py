"""Initialization for the admin package."""

from .core_registers import AcademicYearAdmin, SemAdmin, TermAdmin
from .core_resources import AcademicYearResource, SemResource
from .filters import (
    SecBySemFlt,
    SectionFacultyFltAc,
    SemFltAC,
)
from .inlines import SecIL, SemIL
from .section_registers import SecAdmin
from .section_resources import SecResource
from .session_resources import ScheduleResource, SecSessionResource
from .session_registers import SecSessionAdmin
from .views import SecBySemAutocomplete

__all__ = [
    # Admin
    "AcademicYearAdmin",
    "SecSessionAdmin",
    "SecAdmin",
    "SemAdmin",
    "TermAdmin",
    # Resource
    "AcademicYearResource",
    "SecSessionResource",
    "ScheduleResource",
    "SecResource",
    "SemResource",
    # Inline
    "SecIL",
    "SemIL",
    # Flts
    "SectionBySemesterAutocom",
    "SecBySemFlt",
    "SectionFacultyFltAc",
    "SemFltAC",
]
