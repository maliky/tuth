"""Initialization for the models package."""

from .program import Program
from .college import College
from .concentration import Concentration
from .course import Course
from .curriculum import Curriculum
from .department import Department
from .prerequisite import Prerequisite

__all__ = [
    "Program",
    "College",
    "Concentration",
    "Course",
    "Curriculum",
    "Department",
    "Prerequisite",
]
