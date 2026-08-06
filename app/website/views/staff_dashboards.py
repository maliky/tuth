"""Staff dashboard views."""

from __future__ import annotations

from typing import cast

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect

from app.website.services.staff_portal import (
    ROLE_CONFIG,
    render_role_dashboard,
    resolve_staff_role,
    user_can_access_role,
)
from app.website.services.staff_student_search import (
    dashboard_student_search_results,
    dashboard_student_search_url,
)


@login_required
def staff_dashboard(request: HttpRequest) -> HttpResponse:
    """Route staff users to their highest-priority dashboard."""
    role_slug = resolve_staff_role(request.user)
    return render_role_dashboard(request, role_slug)


@login_required
def staff_role_dashboard(request: HttpRequest, role: str) -> HttpResponse:
    """Allow explicit navigation to a staff dashboard, enforcing membership."""
    if role not in ROLE_CONFIG:
        raise Http404("Unknown staff role.")

    if not user_can_access_role(request.user, role):
        raise PermissionDenied("You do not belong to this staff group.")

    # Keep the self-profile surface canonical; staff/staff should not fork it.
    if role == "staff":
        return redirect("account_profile")

    return render_role_dashboard(request, role)


@login_required
def staff_dashboard_student_search_autocomplete(
    request: HttpRequest,
    role: str,
) -> JsonResponse:
    """Return student suggestions for the current role dashboard."""
    if role not in ROLE_CONFIG:
        raise Http404("Unknown staff role.")
    if not user_can_access_role(request.user, role):
        raise PermissionDenied("You do not belong to this staff group.")
    return JsonResponse(
        {
            "results": dashboard_student_search_results(
                cast(User, request.user),
                role,
                request.GET,
            )
        }
    )


@login_required
def staff_dashboard_student_search(
    request: HttpRequest,
    role: str,
) -> HttpResponse:
    """Redirect a dashboard student search to the selected authorized surface."""
    if role not in ROLE_CONFIG:
        raise Http404("Unknown staff role.")
    if not user_can_access_role(request.user, role):
        raise PermissionDenied("You do not belong to this staff group.")
    try:
        return redirect(
            dashboard_student_search_url(cast(User, request.user), role, request.GET)
        )
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("staff_role_dashboard", role=role)
