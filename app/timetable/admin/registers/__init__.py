"""app.timetable.admin.registers modules"""

from app.timetable.admin.registers.core import AcademicYearAdmin, SemesterAdmin
from app.timetable.admin.registers.reservation import ReservationAdmin
from app.timetable.admin.registers.section import SectionAdmin
from app.timetable.admin.registers.session import SessionAdmin


__all__ = [
    "SectionAdmin",
    "ReservationAdmin",
    "AcademicYearAdmin",
    "SemesterAdmin",
    "SessionAdmin",
]
