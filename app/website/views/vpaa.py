"""VPAA portal workflow views."""

from __future__ import annotations

from typing import cast

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from app.website.services.staff_portal import user_can_access_role
from app.website.services.vpaa_portal import (
    approve_vpaa_approval,
    build_vpaa_approval_detail_context,
    build_vpaa_approvals_context,
    mark_vpaa_approval_in_review,
    reject_vpaa_approval,
)


def _require_vpaa_access(request: HttpRequest) -> User:
    """Return the current user or raise if VPAA access is missing."""
    user = cast(User, request.user)
    if not user_can_access_role(user, "vpaa"):
        raise PermissionDenied("VPAA access required.")
    return user


@login_required
def vpaa_approvals(request: HttpRequest) -> HttpResponse:
    """Render the VPAA approval queue."""
    _require_vpaa_access(request)
    context = build_vpaa_approvals_context(request)
    return render(request, "website/staff/vpaa_approvals.html", context)


@login_required
def vpaa_approval_detail(request: HttpRequest, approval_id: int) -> HttpResponse:
    """Render one VPAA approval request."""
    _require_vpaa_access(request)
    context = build_vpaa_approval_detail_context(request, approval_id)
    return render(request, "website/staff/vpaa_approval_detail.html", context)


@login_required
@require_POST
def vpaa_approval_mark_review(request: HttpRequest, approval_id: int) -> HttpResponse:
    """Mark one VPAA approval as in review."""
    user = _require_vpaa_access(request)
    mark_vpaa_approval_in_review(user=user, approval_id=approval_id)
    messages.info(request, "Approval request marked in review.")
    return redirect("vpaa_approval_detail", approval_id=approval_id)


@login_required
@require_POST
def vpaa_approval_approve(request: HttpRequest, approval_id: int) -> HttpResponse:
    """Approve one VPAA approval request."""
    user = _require_vpaa_access(request)
    notes = request.POST.get("notes", "")
    approve_vpaa_approval(user=user, approval_id=approval_id, notes=notes)
    messages.success(request, "Approval request approved.")
    return redirect("vpaa_approval_detail", approval_id=approval_id)


@login_required
@require_POST
def vpaa_approval_reject(request: HttpRequest, approval_id: int) -> HttpResponse:
    """Reject one VPAA approval request."""
    user = _require_vpaa_access(request)
    notes = request.POST.get("notes", "")
    reject_vpaa_approval(user=user, approval_id=approval_id, notes=notes)
    messages.warning(request, "Approval request rejected.")
    return redirect("vpaa_approval_detail", approval_id=approval_id)
