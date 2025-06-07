"""Initialization for the admin package."""

from .core import AcademicYearAdmin, SectionAdmin, SemesterAdmin
from .inlines import SemesterInline, SectionInline, ReservationInline
from .resources import AcademicYearResource, SectionResource, SemesterResource
from .schedule import ScheduleAdmin

__all__ = [
    "AcademicYearAdmin",
    "SemesterAdmin",
    "SectionAdmin",
    "SemesterInline",
    "SectionInline",
    "SectionResource",
    "AcademicYearResource",
    "SemesterResource",
    "ReservationInline",
    "ScheduleAdmin",
]
