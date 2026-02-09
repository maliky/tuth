"""Initialization for the admin package."""

from .resources import CourseResource, CurriculumCourseResource
from .core import (
    CollegeAdmin,
    CourseAdmin,
    CurriculumCourseRequirementGroupAdmin,
    CurriculumAdmin,
    CurriculumCourseAdmin,
    PrerequisiteAdmin,
)

__all__ = [
    "CourseResource",
    "CurriculumCourseResource",
    "CollegeAdmin",
    "CourseAdmin",
    "CurriculumCourseRequirementGroupAdmin",
    "CurriculumAdmin",
    "CurriculumCourseAdmin",
    "PrerequisiteAdmin",
]
