"""app.timetable.admin.resources modules"""

from app.timetable.admin.resources.core import AcademicYearResource, SemesterResource
from app.timetable.admin.resources.section import SectionResource
from app.timetable.admin.resources.session import SessionResource

__all__ = [
    "SectionResource",
    "SemesterResource",
    "AcademicYearResource",
    "SessionResource",
]
