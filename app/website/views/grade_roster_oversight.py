"""Read-only academic grade roster oversight views."""

from __future__ import annotations

from typing import cast

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render

from app.website.services.grade_roster_oversight import (
    OVERSIGHT_ROLE_SLUGS,
    build_grade_roster_detail_context,
    build_grade_roster_list_context,
    oversight_faculty_results,
    oversight_student_results,
)
from app.website.services.staff_portal import user_can_access_role


def _require_oversight_role(request: HttpRequest, role: str) -> None:
    """Validate that the requested role owns grade-roster oversight."""
    if role not in OVERSIGHT_ROLE_SLUGS:
        raise Http404("Unknown grade roster oversight role.")
    if not user_can_access_role(request.user, role):
        raise PermissionDenied("You do not belong to this academic oversight group.")


@login_required
def staff_grade_rosters(request: HttpRequest, role: str) -> HttpResponse:
    """Render read-only section roster summaries for academic oversight."""
    _require_oversight_role(request, role)
    context = build_grade_roster_list_context(request, role)
    return render(request, "website/staff/grade_roster_oversight.html", context)


@login_required
def staff_grade_roster_detail(
    request: HttpRequest,
    role: str,
    section_id: int,
) -> HttpResponse:
    """Render one read-only section roster and submitted grade list."""
    _require_oversight_role(request, role)
    context = build_grade_roster_detail_context(request, role, section_id)
    return render(request, "website/staff/grade_roster_detail.html", context)


@login_required
def staff_grade_roster_student_autocomplete(
    request: HttpRequest,
    role: str,
) -> HttpResponse:
    """Return student suggestions for academic oversight roster filters."""
    _require_oversight_role(request, role)
    user = cast(User, request.user)
    return JsonResponse(
        {"results": oversight_student_results(user, role, request.GET.get("q"))}
    )


@login_required
def staff_grade_roster_faculty_autocomplete(
    request: HttpRequest,
    role: str,
) -> HttpResponse:
    """Return faculty suggestions for academic oversight roster filters."""
    _require_oversight_role(request, role)
    user = cast(User, request.user)
    return JsonResponse(
        {"results": oversight_faculty_results(user, role, request.GET.get("q"))}
    )


__all__ = [
    "staff_grade_roster_detail",
    "staff_grade_roster_faculty_autocomplete",
    "staff_grade_roster_student_autocomplete",
    "staff_grade_rosters",
]
