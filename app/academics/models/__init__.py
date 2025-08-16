"""Initialization for the models package."""

from .college import College
from .concentration import Major, Minor, MajorProgram, MinorProgram
from .course import Course
from .curriculum import Curriculum
from .curriculum_status import CurriculumStatus
from .credit_hour import CreditHour
from .department import Department
from .prerequisite import Prerequisite
from .program import Program

__all__ = [
    "College",
    "Course",
    "Curriculum",
    "Department",
    "Major",
    "MajorProgram",
    "Minor",
    "MinorProgram",
    "CurriculumStatus",
    "CreditHour",
    "Prerequisite",
    "Program",
]
