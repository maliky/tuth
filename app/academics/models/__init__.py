"""Initialization for the models package."""

from .college import College
from .concentration import Major, Minor, MajorProgram, MinorProgram
from .course import Course
from .curriculum import Curriculum, CurriculumStatus
from .department import Department
from .prerequisite import Prerequisite
from .program import Program

__all__ = [
    "CurriculumStatus",
    "College",
    "Course",
    "Curriculum",
    "Department",
    "Major",
    "MajorProgram",
    "Minor",
    "MinorProgram",
    "Prerequisite",
    "Program",
]
