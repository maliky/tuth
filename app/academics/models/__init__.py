"""Initialization for the models package."""
from .college import College
from .concentration import Major, Minor, MajorCurriculumCourse, MinorCurriculumCourse
from .course import Course, CurriculumCourse
from .curriculum import Curriculum, CurriculumStatus
from .department import Department
from .prerequisite import Prerequisite

__all__ = [
    "CurriculumStatus",
    "College",
    "Course",
    "Curriculum",
    "Department",
    "Major",
    "MajorCurriculumCourse",
    "Minor",
    "MinorCurriculumCourse",
    "Prerequisite",
    "CurriculumCourse",
]
