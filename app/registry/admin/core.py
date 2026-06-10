"""Compatibility façade for registry admin registrations."""

from __future__ import annotations

from app.registry.admin.grade_admin import GradeAdmin, GradeValueAdmin
from app.registry.admin.registration_admin import (
    RegioAdmin,
    RegioAdminForm,
    RegioBulkAddForm,
    _available_secs_for_std,
    _open_regio_sem,
    _resolve_request_std,
    _sec_queryset_for_std,
)
from app.registry.admin.transcript_admin import (
    CurriStatusAdmin,
    RegioStatusAdmin,
    TranscriptRequestAdmin,
)

__all__ = [
    "CurriStatusAdmin",
    "GradeAdmin",
    "GradeValueAdmin",
    "RegioAdmin",
    "RegioAdminForm",
    "RegioBulkAddForm",
    "RegioStatusAdmin",
    "TranscriptRequestAdmin",
    "_available_secs_for_std",
    "_open_regio_sem",
    "_resolve_request_std",
    "_sec_queryset_for_std",
]
