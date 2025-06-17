"""Initialization for the models package."""

from .college import College
from .concentration import Concentration
from .course import Course
from .curriculum import Curriculum
from .curriculum_course import CurriculumCourse
from .prerequisite import Prerequisite
from .department import Department

__all__ = [
    "College",
    "Concentration",
    "Course",
    "CurriculumCourse",
    "Curriculum",
    "Prerequisite",
    "Department",
]
