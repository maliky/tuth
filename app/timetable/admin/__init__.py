"""Initialization for the admin package."""

from app.timetable.admin.registers.core import (
    AcademicYearAdmin,
    SemesterAdmin,
)
from app.timetable.admin.registers.section import SectionAdmin
from app.timetable.admin.registers.session import SessionAdmin
from app.timetable.admin.resources.core import AcademicYearResource, SemesterResource
from app.timetable.admin.resources.section import SectionResource

from .inlines import SectionInline, SemesterInline

__all__ = [
    "AcademicYearAdmin",
    "SemesterAdmin",
    "SectionAdmin",
    "SemesterInline",
    "SectionInline",
    "SectionResource",
    "AcademicYearResource",
    "SemesterResource",
    "SessionAdmin",
]
