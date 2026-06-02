"""Typed services for dean-facing curriculum portal workflows."""

from __future__ import annotations

from typing import TypeAlias, cast

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db.models import QuerySet
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.urls import reverse

from app.academics.models.curriculum import Curriculum
from app.academics.models.curriculum_course import CurriCrs
from app.academics.models.college import College
from app.people.models.faculty import Faculty
from app.shared.models import ApprovalQueue
from app.website.services.staff_portal import (
    build_staff_role_switcher,
    build_staff_sidebar_links,
)

ContextT: TypeAlias = dict[str, object]


def dean_college(user: User) -> College | None:
    """Return the college attached to a dean account, when available."""
    staff = getattr(user, "staff", None)
    if staff is None:
        return None
    try:
        faculty = cast(Faculty, staff.faculty)
    except Faculty.DoesNotExist:
        return None
    return faculty.college


def dean_curriculum_queryset(user: User) -> QuerySet[Curriculum]:
    """Return curricula a dean can review."""
    qs = Curriculum.objects.select_related("college", "status").order_by(
        "college__code", "short_name"
    )
    if user.is_superuser:
        return qs
    college = dean_college(user)
    if college is None:
        return Curriculum.objects.none()
    return qs.filter(college=college)


def _dean_breadcrumb(label: str) -> list[dict[str, str]]:
    """Return breadcrumbs rooted in the dean dashboard."""
    return [
        {
            "label": "Dean oversight",
            "href": reverse("staff_role_dashboard", args=["dean"]),
        },
        {"label": label, "href": ""},
    ]


def _activation_ct() -> ContentType:
    """Return the content type used for curriculum activation requests."""
    return ContentType.objects.get_for_model(Curriculum)


def pending_activation_count(user: User) -> int:
    """Return pending curriculum activation requests visible to a dean."""
    curriculum_ids = list(dean_curriculum_queryset(user).values_list("id", flat=True))
    if not curriculum_ids:
        return 0
    return ApprovalQueue.objects.filter(
        request_type="curriculum_activation",
        target_role="vpaa",
        status__in={"pending", "in_review"},
        related_content_type=_activation_ct(),
        related_object_id__in=curriculum_ids,
    ).count()


def build_dean_curricula_context(request: HttpRequest) -> ContextT:
    """Build context for the dean curriculum list."""
    user = cast(User, request.user)
    curricula = list(dean_curriculum_queryset(user))
    return {
        "page_title": "Curriculum review",
        "page_summary": "Review college curricula and request VPAA activation from Tusis.",
        "eyebrow": "Dean",
        "sidebar_links": build_staff_sidebar_links("dean", "curricula"),
        "role_switcher": build_staff_role_switcher(user, "dean"),
        "breadcrumbs": _dean_breadcrumb("Curriculum review"),
        "curricula": curricula,
        "college": dean_college(user),
        "pending_activation_count": pending_activation_count(user),
    }


def build_dean_curriculum_detail_context(
    request: HttpRequest,
    curriculum_id: int,
) -> ContextT:
    """Build context for one dean curriculum detail page."""
    user = cast(User, request.user)
    curriculum = get_object_or_404(dean_curriculum_queryset(user), pk=curriculum_id)
    programs = list(
        CurriCrs.objects.filter(curriculum=curriculum)
        .select_related("course", "credit_hours")
        .order_by("level_number", "semester_number", "course__short_code")
    )
    existing_request = pending_activation_request(curriculum)
    return {
        "page_title": curriculum.short_name,
        "page_summary": curriculum.long_name or "Curriculum detail",
        "eyebrow": "Dean",
        "sidebar_links": build_staff_sidebar_links("dean", "curricula"),
        "role_switcher": build_staff_role_switcher(user, "dean"),
        "breadcrumbs": _dean_breadcrumb(curriculum.short_name),
        "curriculum": curriculum,
        "programs": programs,
        "existing_request": existing_request,
    }


def pending_activation_request(curriculum: Curriculum) -> ApprovalQueue | None:
    """Return an open activation request for a curriculum, if one exists."""
    return ApprovalQueue.objects.filter(
        request_type="curriculum_activation",
        target_role="vpaa",
        status__in={"pending", "in_review"},
        related_content_type=_activation_ct(),
        related_object_id=curriculum.id,
    ).first()


def request_curriculum_activation(
    *,
    user: User,
    curriculum_id: int,
) -> tuple[ApprovalQueue, bool]:
    """Create or reuse a VPAA activation request for a dean curriculum."""
    curriculum = get_object_or_404(dean_curriculum_queryset(user), pk=curriculum_id)
    if curriculum.status_id == "approved":
        raise ValueError("This curriculum is already approved.")
    existing = pending_activation_request(curriculum)
    if existing is not None:
        return existing, False
    approval = ApprovalQueue.objects.create(
        request_type="curriculum_activation",
        target_role="vpaa",
        submitted_by=user,
        related_content_type=_activation_ct(),
        related_object_id=curriculum.id,
        payload={
            "summary": curriculum.long_name or curriculum.short_name,
            "curriculum": curriculum.short_name,
            "college": curriculum.college.code,
        },
    )
    return approval, True
