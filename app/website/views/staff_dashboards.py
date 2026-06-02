"""Staff dashboard views."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse

from app.website.services.staff_portal import (
    ROLE_CONFIG,
    render_role_dashboard,
    resolve_staff_role,
    user_can_access_role,
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

    return render_role_dashboard(request, role)
