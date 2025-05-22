from .admin import CollegeAdmin, CourseAdmin, CurriculumAdmin, PrerequisiteAdmin
from .models import (
    College,
    Concentration,
    Course,
    Curriculum,
    CurriculumCourse,
    Prerequisite,
)

__all__ = [
    # models
    "Course",
    "College",
    "Curriculum",
    "CurriculumCourse",
    "Prerequisite",
    "Concentration",
    # admin
    "CollegeAdmin",
    "CurriculumAdmin",
    "CourseAdmin",
    "PrerequisiteAdmin",
]
