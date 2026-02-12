"""Initialization for the admin package."""

from .resources import CourseResource, CurriCourseResource
from .core import (
    CollegeAdmin,
    CourseAdmin,
    CurriAdmin,
    CurriCourseAdmin,
    PrerequisiteAdmin,
    CurriStdEnrollAdmin,
)

__all__ = [
    "CourseResource",
    "CurriCourseResource",
    "CollegeAdmin",
    "CourseAdmin",
    "CurriAdmin",
    "CurriCourseAdmin",
    "PrerequisiteAdmin",
    "CurriStdEnrollAdmin",
]
