"""app.timetable.admin.resources modules."""

from .core import SemesterResource, AcademicYearResource
from .section import SectionResource
from .session import ScheduleResource, SecSessionResource

__all__ = [
    "AcademicYearResource" "SemesterResource",
    "SectionResource",
    "ScheduleResource",
    "SecSessionResource",
]
