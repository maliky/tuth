"""Initialization for the models package."""

from .college import College
from .concentration import Major, MajorCurriculumCourse, Minor, MinorCurriculumCourse
from .course import Course, CurriculumCourse
from .curriculum import Curriculum, CurriculumStatus
from .department import Department
from .prerequisite import Prerequisite

__all__ = [
    "College",
    "Course",
    "Curriculum",
    "CurriculumCourse",
    "CurriculumStatus",
    "Department",
    "Major",
    "MajorCurriculumCourse",
    "Minor",
    "MinorCurriculumCourse",
    "Prerequisite",
]
