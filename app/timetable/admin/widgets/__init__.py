"""app.timetable.admin.widgets module"""

from app.timetable.admin.widgets.core import (
    AcademicYearCodeWidget,
    SemesterCodeWidget,
    SemesterWidget,
)
from app.timetable.admin.widgets.section import SectionCodeWidget, SectionWidget
from app.timetable.admin.widgets.session import (
    ScheduleWidget,
    SessionWidget,
    WeekdayWidget,
)


__all__ = [
    "SectionWidget",
    "SectionCodeWidget",
    "AcademicYearCodeWidget",
    "SemesterWidget",
    "SemesterCodeWidget",
    "SessionWidget",
    "ScheduleWidget",
    "WeekdayWidget",
]
