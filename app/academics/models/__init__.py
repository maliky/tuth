"""Initialization for the models package."""

from .college import College
from .concentration import Major, MajorCurriCourse, Minor, MinorCurriCourse
from .course import Course
from .curriculum import Curriculum, CurriStatus
from .curriculum_course import CurriCourse
from .department import Department
from .prerequisite import Prerequisite
from .requirement_group import (
    CurriCourseReqGp,
    CurriCourseReqMember,
    ReqKind,
)
from .student_curriculum_enrollment import CurriStdEnroll

__all__ = [
    "College",
    "Course",
    "Curriculum",
    "CurriCourse",
    "CurriStatus",
    "Department",
    "Major",
    "MajorCurriCourse",
    "Minor",
    "MinorCurriCourse",
    "Prerequisite",
    "CurriCourseReqGp",
    "CurriCourseReqMember",
    "ReqKind",
    "CurriStdEnroll",
]
