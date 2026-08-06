"""Student quick-search helpers for staff role dashboards."""

from __future__ import annotations

from typing import TypedDict
from urllib.parse import urlencode

from django.contrib.auth.models import User
from django.db.models import Q, QuerySet
from django.http import QueryDict
from django.urls import reverse

from app.academics.career_scope import (
    CareerModeT,
    filter_by_academic_career,
    selected_academic_career,
)
from app.people.models.student import Student
from app.shared.utils import parse_str


class StudentSearchActionT(TypedDict):
    """One destination option for dashboard student search."""

    value: str
    label: str


class StudentSearchContextT(TypedDict):
    """Template context for the dashboard student search form."""

    action_url: str
    autocomplete_url: str
    selected_academic_career: CareerModeT
    actions: list[StudentSearchActionT]


class StudentSearchResultT(TypedDict):
    """Select2-compatible student search result."""

    id: int
    text: str


ROLE_ACTIONS: dict[str, tuple[StudentSearchActionT, ...]] = {
    "faculty": ({"value": "faculty_sections", "label": "My grade rosters"},),
    "chair": (
        {"value": "oversight_rosters", "label": "Grade rosters"},
        {"value": "oversight_transcripts", "label": "Grade transcripts"},
    ),
    "dean": (
        {"value": "oversight_rosters", "label": "Grade rosters"},
        {"value": "oversight_transcripts", "label": "Grade transcripts"},
    ),
    "vpaa": (
        {"value": "oversight_transcripts", "label": "Grade transcripts"},
        {"value": "oversight_rosters", "label": "Grade rosters"},
    ),
    "registrar": (
        {"value": "registrar_grades", "label": "Grades"},
        {"value": "registrar_rosters", "label": "Class rosters"},
    ),
    "reg_officer": (
        {"value": "registrar_grades", "label": "Grades"},
        {"value": "registrar_rosters", "label": "Class rosters"},
    ),
    "enrollment": (
        {"value": "enrollment_profile", "label": "Student profile"},
        {"value": "enrollment_directory", "label": "Directory"},
    ),
    "enrollment_officer": (
        {"value": "enrollment_profile", "label": "Student profile"},
        {"value": "enrollment_directory", "label": "Directory"},
    ),
    "finance": (
        {"value": "finance_invoices", "label": "Invoices"},
        {"value": "finance_payments", "label": "Payments"},
    ),
    "finance_officer": (
        {"value": "finance_invoices", "label": "Invoices"},
        {"value": "finance_payments", "label": "Payments"},
    ),
    "cashier": (
        {"value": "finance_payments", "label": "Payments"},
        {"value": "finance_invoices", "label": "Invoices"},
    ),
}


def dashboard_student_search_context(
    role_slug: str,
    career: CareerModeT,
) -> StudentSearchContextT | None:
    """Return dashboard student search context for roles with student workflows."""
    actions = list(ROLE_ACTIONS.get(role_slug, ()))
    if not actions:
        return None
    return {
        "action_url": reverse("staff_dashboard_student_search", args=[role_slug]),
        "autocomplete_url": reverse(
            "staff_dashboard_student_search_autocomplete",
            args=[role_slug],
        ),
        "selected_academic_career": career,
        "actions": actions,
    }


def _student_label(student: Student) -> str:
    """Return a compact label for student search results."""
    name = student.long_name or student.user.get_full_name() or student.user.username
    student_id = student.student_id or "Pending ID"
    return f"{student_id} - {name}"


def _base_student_scope(career: CareerModeT) -> QuerySet[Student]:
    """Return students in the selected career."""
    return filter_by_academic_career(
        Student.objects.select_related("user"),
        "academic_career",
        career,
    )


def _filter_student_query(
    queryset: QuerySet[Student],
    query: str,
) -> QuerySet[Student]:
    """Apply the common student text search filter."""
    return queryset.filter(
        Q(student_id__icontains=query)
        | Q(long_name__icontains=query)
        | Q(user__first_name__icontains=query)
        | Q(user__last_name__icontains=query)
        | Q(user__username__icontains=query)
    )


def _faculty_student_scope(user: User, career: CareerModeT) -> QuerySet[Student]:
    """Return students registered in sections assigned to this faculty user."""
    from app.website.services.faculty_grade_portal import (
        assigned_sections_for_faculty,
    )
    from app.website.services.staff_common import get_faculty_profile

    faculty = get_faculty_profile(user)
    if faculty is None:
        return Student.objects.none()
    section_ids = assigned_sections_for_faculty(faculty, career).values_list(
        "id",
        flat=True,
    )
    return _base_student_scope(career).filter(
        student_registrations__section_id__in=section_ids,
    )


def _oversight_student_scope(
    user: User,
    role_slug: str,
    career: CareerModeT,
) -> QuerySet[Student]:
    """Return students visible through a chair/dean/VPAA grade scope."""
    from app.website.services.grade_roster_oversight import (
        scoped_grade_roster_sections,
    )

    section_ids = scoped_grade_roster_sections(user, role_slug, career).values_list(
        "id",
        flat=True,
    )
    return _base_student_scope(career).filter(
        Q(student_registrations__section_id__in=section_ids)
        | Q(grade__section_id__in=section_ids)
    )


def _registrar_student_scope(career: CareerModeT) -> QuerySet[Student]:
    """Return students with registrar-visible records in the selected career."""
    return _base_student_scope(career).filter(
        Q(grade__isnull=False) | Q(student_registrations__isnull=False)
    )


def _finance_student_scope(career: CareerModeT) -> QuerySet[Student]:
    """Return finance-relevant students in the selected career."""
    from app.website.services.finance_portal import finance_relevant_std_qs

    return finance_relevant_std_qs(career)


def _student_scope_for_role(
    user: User,
    role_slug: str,
    career: CareerModeT,
) -> QuerySet[Student]:
    """Return students searchable from one role dashboard."""
    if role_slug == "faculty":
        return _faculty_student_scope(user, career)
    if role_slug in {"chair", "dean", "vpaa"}:
        return _oversight_student_scope(user, role_slug, career)
    if role_slug in {"registrar", "reg_officer"}:
        return _registrar_student_scope(career)
    if role_slug in {"finance", "finance_officer", "cashier"}:
        return _finance_student_scope(career)
    if role_slug in {"enrollment", "enrollment_officer"}:
        return _base_student_scope(career)
    return Student.objects.none()


def dashboard_student_search_results(
    user: User,
    role_slug: str,
    params: QueryDict,
) -> list[StudentSearchResultT]:
    """Return Select2 student suggestions for a role dashboard."""
    query = parse_str(params.get("q"))
    if not query:
        return []
    career = selected_academic_career(params)
    students = (
        _filter_student_query(_student_scope_for_role(user, role_slug, career), query)
        .distinct()
        .order_by("long_name", "student_id")[:15]
    )
    return [{"id": student.id, "text": _student_label(student)} for student in students]


def _student_for_role(
    user: User,
    role_slug: str,
    career: CareerModeT,
    student_id: int,
) -> Student | None:
    """Return a selected student only when visible from the role scope."""
    return (
        _student_scope_for_role(user, role_slug, career)
        .filter(pk=student_id)
        .distinct()
        .first()
    )


def _with_query(route_name: str, query: dict[str, str], *args: object) -> str:
    """Return a reversed URL with encoded query parameters."""
    return f"{reverse(route_name, args=args)}?{urlencode(query)}"


def _target_url(
    action: str, role_slug: str, student: Student, career: CareerModeT
) -> str:
    """Return the portal destination URL for a dashboard student action."""
    student_id = str(student.id)
    base_query = {"academic_career": career, "student_id": student_id}
    if action == "faculty_sections":
        return _with_query("faculty_grade_sections", base_query)
    if action == "oversight_rosters":
        return _with_query(
            "staff_grade_rosters",
            {**base_query, "semester": "all"},
            role_slug,
        )
    if action == "oversight_transcripts":
        return _with_query(
            "staff_grade_transcripts",
            {**base_query, "semester": "all"},
            role_slug,
        )
    if action == "registrar_grades":
        return _with_query("reg_grades_dashboard", {**base_query, "semester": "all"})
    if action == "registrar_rosters":
        return _with_query("reg_class_rosters", {**base_query, "semester": "all"})
    if action == "enrollment_profile":
        return _with_query("std_detail", {"academic_career": career}, student.id)
    if action == "enrollment_directory":
        query = {"academic_career": career, "q": student.student_id or student.long_name}
        return _with_query("std_list", query)
    if action == "finance_invoices":
        query = {
            "academic_career": career,
            "student_id": student_id,
            "semester": "all",
            "invoice_status": "all",
        }
        return _with_query("finance_officer_invoices", query)
    if action == "finance_payments":
        query = {
            "academic_career": career,
            "tab": "payments",
            "student_id": student_id,
            "semester": "all",
            "payment_status": "all",
        }
        return _with_query("finance_officer_invoices", query)
    raise ValueError("Choose a valid student search target.")


def dashboard_student_search_url(
    user: User,
    role_slug: str,
    params: QueryDict,
) -> str:
    """Return the destination URL for a dashboard student search submission."""
    career = selected_academic_career(params)
    action = parse_str(params.get("student_target"))
    allowed_actions = {item["value"] for item in ROLE_ACTIONS.get(role_slug, ())}
    if action not in allowed_actions:
        raise ValueError("Choose what to open for the selected student.")
    raw_student_id = parse_str(params.get("student_id"))
    if not raw_student_id:
        raise ValueError("Choose a student from the search results.")
    try:
        student_id = int(raw_student_id)
    except ValueError as exc:
        raise ValueError("Choose a student from the search results.") from exc
    student = _student_for_role(user, role_slug, career, student_id)
    if student is None:
        raise ValueError("The selected student is not available in this career scope.")
    return _target_url(action, role_slug, student, career)


__all__ = [
    "StudentSearchActionT",
    "StudentSearchContextT",
    "StudentSearchResultT",
    "dashboard_student_search_context",
    "dashboard_student_search_results",
    "dashboard_student_search_url",
]
