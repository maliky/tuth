"""Dean portal workflow views."""

from __future__ import annotations

from typing import cast

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from app.website.services.dean_portal import (
    build_dean_curricula_context,
    build_dean_curriculum_detail_context,
    request_curriculum_activation,
)
from app.website.services.staff_portal import user_can_access_role


def _require_dean_access(request: HttpRequest) -> User:
    """Return the current user or raise if they cannot access dean workflows."""
    user = cast(User, request.user)
    if not user_can_access_role(user, "dean"):
        raise PermissionDenied("Dean access required.")
    return user


@login_required
def dean_curricula(request: HttpRequest) -> HttpResponse:
    """Render curricula visible to the current dean."""
    _require_dean_access(request)
    context = build_dean_curricula_context(request)
    return render(request, "website/staff/dean_curricula.html", context)


@login_required
def dean_curriculum_detail(request: HttpRequest, curriculum_id: int) -> HttpResponse:
    """Render one curriculum visible to the current dean."""
    _require_dean_access(request)
    context = build_dean_curriculum_detail_context(request, curriculum_id)
    return render(request, "website/staff/dean_curriculum_detail.html", context)


@login_required
@require_POST
def dean_curriculum_request_activation(
    request: HttpRequest,
    curriculum_id: int,
) -> HttpResponse:
    """Request VPAA activation for a dean-visible curriculum."""
    user = _require_dean_access(request)
    try:
        _approval, created = request_curriculum_activation(
            user=user,
            curriculum_id=curriculum_id,
        )
    except ValueError as exc:
        messages.warning(request, str(exc))
    else:
        if created:
            messages.success(request, "Curriculum activation request sent to VPAA.")
        else:
            messages.info(request, "A VPAA activation request is already open.")
    return redirect("dean_curriculum_detail", curriculum_id=curriculum_id)
