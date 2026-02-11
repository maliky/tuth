"""Initialization for the admin package."""

from .resources import CourseResource, CurriculumCourseResource
from .core import (
    CollegeAdmin,
    CourseAdmin,
    CurriculumAdmin,
    CurriculumCourseAdmin,
    PrerequisiteAdmin,
    StudentCurriculumEnrollmentAdmin,
)

__all__ = [
    "CourseResource",
    "CurriculumCourseResource",
    "CollegeAdmin",
    "CourseAdmin",
    "CurriculumAdmin",
    "CurriculumCourseAdmin",
    "PrerequisiteAdmin",
    "StudentCurriculumEnrollmentAdmin",
]
