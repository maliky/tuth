"""Initialization for the models package."""

from .college import College
from .concentration import Major, MajorCurriCrs, Minor, MinorCurriCrs
from .course import Course
from .curriculum import Curriculum, CurriStatus
from .curriculum_course import CurriCrs
from .department import Department
from .prerequisite import Prerequisite
from .requirement_group import (
    CurriCrsReqGp,
    CurriCrsReqMember,
    ReqKind,
)
from .student_curriculum_enrollment import CurriStdEnroll

__all__ = [
    "College",
    "Course",
    "Curriculum",
    "CurriCrs",
    "CurriStatus",
    "Department",
    "Major",
    "MajorCurriCrs",
    "Minor",
    "MinorCurriCrs",
    "Prerequisite",
    "CurriCrsReqGp",
    "CurriCrsReqMember",
    "ReqKind",
    "CurriStdEnroll",
]
