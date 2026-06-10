"""Compatibility façade for academics admin registrations."""

from __future__ import annotations

from app.academics.admin.course_admin import CrsAdmin
from app.academics.admin.curriculum_admin import CurriAdmin, CurriMergeConflictForm
from app.academics.admin.curriculum_course_admin import CurriCrsAdmin
from app.academics.admin.curriculum_enrollment_admin import CurriStdEnrollAdmin
from app.academics.admin.organization_admin import (
    CollegeAdmin,
    CurriStatusAdmin,
    DptAdmin,
    PrerequisiteAdmin,
)

__all__ = [
    "CollegeAdmin",
    "CrsAdmin",
    "CurriAdmin",
    "CurriCrsAdmin",
    "CurriMergeConflictForm",
    "CurriStatusAdmin",
    "CurriStdEnrollAdmin",
    "DptAdmin",
    "PrerequisiteAdmin",
]
