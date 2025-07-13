"""Initialization for the models package."""

from .college import College
from .concentration import Major, Minor, MajorProgram, MinorProgram
from .course import Course
from .curriculum import Curriculum
from .department import Department
from .prerequisite import Prerequisite
from .program import Program

__all__ = [
    "College",
    "Concentration",
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
