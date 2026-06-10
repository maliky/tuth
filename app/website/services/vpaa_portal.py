"""VPAA portal services for institution-level approval workflows."""

from __future__ import annotations

from typing import TypeAlias, cast

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import QuerySet
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone

from app.academics.models.curriculum import Curriculum
from app.shared.models import ApprovalQueue
from app.website.services.portal_types import BreadcrumbT, PortalContextT
from app.website.services.staff_portal import (
    build_staff_role_switcher,
    build_staff_sidebar_links,
)

ApprovalStatusSetT: TypeAlias = set[str]
UpdateFieldListT: TypeAlias = list[str]

OPEN_APPROVAL_STATUSES: ApprovalStatusSetT = {"pending", "in_review"}


def vpaa_approval_queryset() -> QuerySet[ApprovalQueue]:
    """Return approval requests owned by the VPAA workspace."""
    return ApprovalQueue.objects.filter(target_role="vpaa").select_related(
        "submitted_by",
        "decided_by",
        "related_content_type",
    )


def _vpaa_approval_mutation_queryset() -> QuerySet[ApprovalQueue]:
    """Return a lockable VPAA approval queryset without nullable joins."""
    return ApprovalQueue.objects.filter(target_role="vpaa")


def _vpaa_breadcrumb(label: str) -> list[BreadcrumbT]:
    """Return breadcrumbs rooted in the VPAA dashboard."""
    return [
        {
            "label": "VPAA approval hub",
            "href": reverse("staff_role_dashboard", args=["vpaa"]),
        },
        {"label": label, "href": ""},
    ]


def _approval_curriculum(approval: ApprovalQueue) -> Curriculum | None:
    """Return the related curriculum when the request is curriculum activation."""
    if approval.request_type != "curriculum_activation":
        return None
    related_object = approval.related_object
    if isinstance(related_object, Curriculum):
        return related_object
    return None


def build_vpaa_approvals_context(request: HttpRequest) -> PortalContextT:
    """Build the VPAA approval queue context."""
    user = cast(User, request.user)
    approvals = list(vpaa_approval_queryset().order_by("status", "-created_at"))
    open_count = sum(
        1 for approval in approvals if approval.status in OPEN_APPROVAL_STATUSES
    )
    return {
        "page_title": "Institution approvals",
        "page_summary": "Review curriculum activation and policy requests inside Tusis.",
        "eyebrow": "VPAA",
        "sidebar_links": build_staff_sidebar_links("vpaa", "approvals"),
        "role_switcher": build_staff_role_switcher(user, "vpaa"),
        "breadcrumbs": _vpaa_breadcrumb("Institution approvals"),
        "approvals": approvals,
        "open_count": open_count,
        "decided_count": len(approvals) - open_count,
    }


def build_vpaa_approval_detail_context(
    request: HttpRequest,
    approval_id: int,
) -> PortalContextT:
    """Build context for one VPAA approval request."""
    user = cast(User, request.user)
    approval = get_object_or_404(vpaa_approval_queryset(), pk=approval_id)
    curriculum = _approval_curriculum(approval)
    return {
        "page_title": approval.get_request_type_display(),
        "page_summary": str(approval.payload.get("summary", "Approval request")),
        "eyebrow": "VPAA",
        "sidebar_links": build_staff_sidebar_links("vpaa", "approvals"),
        "role_switcher": build_staff_role_switcher(user, "vpaa"),
        "breadcrumbs": _vpaa_breadcrumb("Request detail"),
        "approval": approval,
        "curriculum": curriculum,
        "can_decide": approval.status in OPEN_APPROVAL_STATUSES,
    }


def _set_approval_status(
    approval: ApprovalQueue,
    *,
    status: str,
    user: User,
    notes: str = "",
    decided: bool = False,
) -> ApprovalQueue:
    """Persist an approval status transition and audit history entry."""
    approval.status = status
    if notes.strip():
        approval.notes = notes.strip()
    update_fields: UpdateFieldListT = ["status", "notes", "updated_at"]
    if decided:
        approval.decided_by = user
        approval.decided_at = timezone.now()
        update_fields.extend(["decided_by", "decided_at"])
    approval.save(update_fields=update_fields)
    approval.status_history.create(status=status, author=user)
    return approval


@transaction.atomic
def mark_vpaa_approval_in_review(*, user: User, approval_id: int) -> ApprovalQueue:
    """Move a VPAA approval request from pending to in-review."""
    approval = get_object_or_404(
        _vpaa_approval_mutation_queryset().select_for_update(),
        pk=approval_id,
        status__in=OPEN_APPROVAL_STATUSES,
    )
    if approval.status == "in_review":
        return approval
    return _set_approval_status(approval, status="in_review", user=user)


@transaction.atomic
def approve_vpaa_approval(
    *,
    user: User,
    approval_id: int,
    notes: str = "",
) -> ApprovalQueue:
    """Approve a VPAA request and apply supported domain side effects."""
    approval = get_object_or_404(
        _vpaa_approval_mutation_queryset().select_for_update(),
        pk=approval_id,
        status__in=OPEN_APPROVAL_STATUSES,
    )
    curriculum = _approval_curriculum(approval)
    if curriculum is not None:
        curriculum.status_id = "approved"
        curriculum.is_active = True
        curriculum.save(update_fields=["status", "is_active"])
    return _set_approval_status(
        approval,
        status="approved",
        user=user,
        notes=notes,
        decided=True,
    )


@transaction.atomic
def reject_vpaa_approval(
    *,
    user: User,
    approval_id: int,
    notes: str = "",
) -> ApprovalQueue:
    """Reject a VPAA request without changing the related domain object."""
    approval = get_object_or_404(
        _vpaa_approval_mutation_queryset().select_for_update(),
        pk=approval_id,
        status__in=OPEN_APPROVAL_STATUSES,
    )
    return _set_approval_status(
        approval,
        status="rejected",
        user=user,
        notes=notes,
        decided=True,
    )


__all__ = [
    "OPEN_APPROVAL_STATUSES",
    "approve_vpaa_approval",
    "build_vpaa_approval_detail_context",
    "build_vpaa_approvals_context",
    "mark_vpaa_approval_in_review",
    "reject_vpaa_approval",
    "vpaa_approval_queryset",
]
