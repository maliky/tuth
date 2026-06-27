"""Typed services for dean-facing curriculum portal workflows."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import TypeAlias, cast

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db.models import QuerySet
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.text import slugify

from app.academics.models.curriculum import Curriculum
from app.academics.models.curriculum_course import CurriCrs
from app.academics.models.college import College
from app.people.models.faculty import Faculty
from app.people.models.student_curriculum_enrollment import StdCurriEnroll
from app.shared.models import ApprovalQueue
from app.website.services.portal_types import PortalContextT
from app.website.services.staff_portal import (
    build_staff_role_switcher,
    build_staff_sidebar_links,
)

ContextT: TypeAlias = PortalContextT
CourseGroupT: TypeAlias = dict[str, object]


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


def _count_rows_by_curriculum(rows: list[tuple[int, int]]) -> dict[int, int]:
    """Return row counts keyed by curriculum id."""
    counts: dict[int, int] = {}
    for curriculum_id, _row_id in rows:
        counts[curriculum_id] = counts.get(curriculum_id, 0) + 1
    return counts


def _attach_curriculum_list_counts(curricula: list[Curriculum]) -> None:
    """Attach student and course counts used by the dean curriculum table."""
    curriculum_ids = [curriculum.id for curriculum in curricula if curriculum.id]
    active_student_rows = list(
        StdCurriEnroll.objects.filter(
            curriculum_id__in=curriculum_ids,
            is_active=True,
            is_primary=True,
        ).values_list("curriculum_id", "student_id")
    )
    course_rows = list(
        CurriCrs.objects.filter(curriculum_id__in=curriculum_ids).values_list(
            "curriculum_id",
            "id",
        )
    )
    active_student_counts = _count_rows_by_curriculum(active_student_rows)
    course_counts = _count_rows_by_curriculum(course_rows)
    for curriculum in curricula:
        # Attach display-only counts without using annotate(), which breaks local mypy.
        curriculum.__dict__["active_student_count"] = active_student_counts.get(
            curriculum.id,
            0,
        )
        curriculum.__dict__["programmed_course_count"] = course_counts.get(
            curriculum.id,
            0,
        )


def _curriculum_sort_key(curriculum: Curriculum) -> tuple[int, int, str]:
    """Return stable ordering with official curricula first."""
    status_rank = 0 if curriculum.status_id == "approved" else 1
    active_rank = 0 if curriculum.is_active else 1
    return (status_rank, active_rank, curriculum.short_name)


def _is_primary_curriculum(curriculum: Curriculum) -> bool:
    """Return whether a curriculum should be in the main dean list."""
    return curriculum.status_id == "approved" and curriculum.is_active


def _level_label(level_number: int | None) -> str:
    """Return a readable curriculum-course level label."""
    if level_number is None or int(level_number) == 99:
        return "Undefined level"
    level = int(level_number)
    if level <= 0:
        return "Remedial"
    year = (level - 1) // 2 + 1
    semester = 1 if level % 2 else 2
    return f"Level {level} (Year {year} Semester {semester})"


def _program_credits(program: CurriCrs) -> int:
    """Return curriculum-course credits as an integer."""
    return int(program.credit_hours.code if program.credit_hours_id else 0)


def _course_groups(programs: list[CurriCrs]) -> list[CourseGroupT]:
    """Group programmed courses by level with semester credit summaries."""
    grouped: dict[int, list[CurriCrs]] = defaultdict(list)
    for program in programs:
        grouped[int(program.level_number or 99)].append(program)

    groups: list[CourseGroupT] = []
    for level_number in sorted(grouped):
        courses = sorted(
            grouped[level_number],
            key=lambda row: (
                int(row.semester_number or 0),
                row.course.short_code or row.course.code,
            ),
        )
        semester_totals: dict[int, int] = defaultdict(int)
        year_totals: dict[int, int] = defaultdict(int)
        total_credits = 0
        for course in courses:
            credits = _program_credits(course)
            semester_totals[int(course.semester_number or 0)] += credits
            year_totals[int(course.year_number or 99)] += credits
            total_credits += credits
        groups.append(
            {
                "label": _level_label(level_number),
                "courses": courses,
                "credits": total_credits,
                "semester_totals": [
                    {
                        "label": f"Semester {semester}" if semester else "Unscheduled",
                        "credits": credits,
                    }
                    for semester, credits in sorted(semester_totals.items())
                ],
                "year_totals": [
                    {
                        "label": f"Year {year}" if year != 99 else "Undefined year",
                        "credits": credits,
                    }
                    for year, credits in sorted(year_totals.items())
                ],
            }
        )
    return groups


def _curriculum_credit_total(programs: list[CurriCrs]) -> int:
    """Return total mapped credits for a curriculum."""
    return sum(_program_credits(program) for program in programs)


def _prereq_graph_context(curriculum: Curriculum) -> dict[str, object]:
    """Return prerequisite graph state without exporting new files."""
    slug = slugify(curriculum.short_name, allow_unicode=False) or str(curriculum.pk)
    json_path = Path(settings.MEDIA_ROOT) / "Prereq" / f"{slug}.json"
    view_url = reverse("academics_prereq_graph", args=[slug])
    return {
        "available": json_path.exists(),
        "view_url": view_url,
        "embed_url": view_url,
        "slug": slug,
    }


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
    curricula = sorted(dean_curriculum_queryset(user), key=_curriculum_sort_key)
    _attach_curriculum_list_counts(curricula)
    primary_curricula = [
        curriculum for curriculum in curricula if _is_primary_curriculum(curriculum)
    ]
    secondary_curricula = [
        curriculum for curriculum in curricula if not _is_primary_curriculum(curriculum)
    ]
    return {
        "page_title": "Curriculum review",
        "page_summary": "Review college curricula and request VPAA activation from Tusis.",
        "eyebrow": "Dean",
        "sidebar_links": build_staff_sidebar_links("dean", "curricula"),
        "role_switcher": build_staff_role_switcher(user, "dean"),
        "breadcrumbs": _dean_breadcrumb("Curriculum review"),
        "curricula": curricula,
        "primary_curricula": primary_curricula,
        "secondary_curricula": secondary_curricula,
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
        "course_groups": _course_groups(programs),
        "credit_total": _curriculum_credit_total(programs),
        "prereq_graph": _prereq_graph_context(curriculum),
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
