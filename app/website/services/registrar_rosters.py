"""Registrar read-only class roster services."""

from __future__ import annotations

from collections import Counter
from typing import TypeAlias, TypedDict, cast

from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Q, QuerySet
from django.http import HttpRequest, QueryDict
from django.shortcuts import get_object_or_404
from django.urls import reverse

from app.people.models.faculty import Faculty
from app.people.models.student import Student
from app.registry.models.grade import Grade
from app.registry.models.registration import Registration
from app.shared.utils import parse_str
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester
from app.website.services.portal_types import BreadcrumbT, PortalContextT
from app.website.services.registrar_portal import registrar_sidebar_role
from app.website.services.staff_common import _admin_shortcuts_for_models
from app.website.services.staff_contexts import REGISTRAR_ADMIN_SHORTCUTS
from app.website.services.staff_portal import (
    build_staff_role_switcher,
    build_staff_sidebar_links,
)

ROSTER_PAGE_SIZE = 50

SectionQueryT: TypeAlias = QuerySet[Section]


class FilterOptionT(TypedDict):
    """One HTML select option for roster filters."""

    value: str
    label: str
    selected: bool


class AutocompleteResultT(TypedDict):
    """Select2-compatible autocomplete item."""

    id: int
    text: str


class RegistrarRosterSummaryRowT(TypedDict):
    """One section row in the registrar class-roster summary."""

    section: Section
    course_code: str
    course_title: str
    faculty_label: str
    roster_count: int
    graded_count: int
    pending_count: int
    grade_entry_open: bool
    detail_url: str


class RegistrarRosterStudentRowT(TypedDict):
    """One student row in a registrar class roster."""

    student_label: str
    student_id: str
    gender: str
    age: str
    registration_status: str
    grade_code: str
    grade_status: str


def clean_int(value: str | None) -> int | None:
    """Return an integer for a clean query parameter, otherwise None."""
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _display_value(value: object) -> str:
    """Return a stable display value for roster templates."""
    if value is None:
        return "Not set"
    text = str(value).strip()
    return text or "Not set"


def _course_code(section: Section) -> str:
    """Return a familiar course code for section lists."""
    course = section.curriculum_course.course
    return course.short_code or course.code or str(course)


def _student_label(student: Student) -> str:
    """Return a concise roster student label."""
    return student.long_name or student.user.get_full_name() or student.username


def _faculty_label(faculty: Faculty | None) -> str:
    """Return a concise faculty label for filters and section rows."""
    if faculty is None:
        return "Unassigned"
    staff = faculty.staff_profile
    user = staff.user
    name = staff.long_name or user.get_full_name() or user.username
    identifier = staff.staff_id or user.username
    return f"{name} ({identifier})"


def _base_section_queryset() -> SectionQueryT:
    """Return hydrated sections for registrar roster pages."""
    return Section.objects.select_related(
        "faculty__staff_profile__user",
        "faculty__staff_profile__department",
        "faculty__college",
        "semester__academic_year",
        "semester__status",
        "curriculum_course__course__department__college",
        "curriculum_course__course",
    )


def _filtered_sections(params: QueryDict) -> SectionQueryT:
    """Apply registrar class-roster filters to the base queryset."""
    selected_student_id = clean_int(params.get("student_id"))
    selected_faculty_id = clean_int(params.get("faculty_id"))
    semester_param = params.get("semester")
    semester_id = None if semester_param == "all" else clean_int(semester_param)
    sections = _base_section_queryset()
    if selected_student_id:
        sections = sections.filter(section_registrations__student_id=selected_student_id)
    if selected_faculty_id:
        sections = sections.filter(faculty_id=selected_faculty_id)
    if semester_id:
        sections = sections.filter(semester_id=semester_id)
    return sections.distinct()


def _semester_options(semester_id: int | None) -> list[FilterOptionT]:
    """Return semester filter options for the registrar roster page."""
    options: list[FilterOptionT] = [
        {"value": "all", "label": "All semesters", "selected": semester_id is None}
    ]
    semesters = Semester.objects.select_related("academic_year").order_by(
        "-academic_year__start_date",
        "-number",
    )
    for semester in semesters:
        options.append(
            {
                "value": str(semester.id),
                "label": f"{semester.academic_year.code} · Semester {semester.number}",
                "selected": semester.id == semester_id,
            }
        )
    return options


def _pagination_hidden_fields(params: QueryDict) -> tuple[str, list[dict[str, str]]]:
    """Return encoded query and hidden fields preserving roster filters."""
    pagination_params = params.copy()
    pagination_params.pop("page", None)
    hidden_fields: list[dict[str, str]] = []
    for key, values in pagination_params.lists():
        for value in values:
            hidden_fields.append({"name": key, "value": value})
    return pagination_params.urlencode(), hidden_fields


def _student_filter_label(student_id: int | None) -> str:
    """Return the label for the currently selected student filter."""
    if student_id is None:
        return ""
    student = Student.objects.select_related("user").filter(pk=student_id).first()
    if student is None:
        return ""
    return f"{student.student_id} — {_student_label(student)}"


def _faculty_filter_label(faculty_id: int | None) -> str:
    """Return the label for the currently selected faculty filter."""
    if faculty_id is None:
        return ""
    faculty = (
        Faculty.objects.select_related("staff_profile__user")
        .filter(pk=faculty_id)
        .first()
    )
    return _faculty_label(faculty) if faculty else ""


def _section_counts(section_ids: list[int]) -> tuple[dict[int, int], dict[int, int]]:
    """Return roster and graded counts keyed by section id."""
    roster_counter = Counter(
        int(section_id)
        for section_id in Registration.objects.filter(
            section_id__in=section_ids
        ).values_list("section_id", flat=True)
    )
    graded_counter = Counter(
        int(section_id)
        for section_id in Grade.objects.filter(
            section_id__in=section_ids,
            value__isnull=False,
        ).values_list("section_id", flat=True)
    )
    return dict(roster_counter), dict(graded_counter)


def _summary_row(
    section: Section,
    roster_counts: dict[int, int],
    graded_counts: dict[int, int],
) -> RegistrarRosterSummaryRowT:
    """Return one rendered section summary row."""
    roster_count = roster_counts.get(section.id, 0)
    graded_count = graded_counts.get(section.id, 0)
    return {
        "section": section,
        "course_code": _course_code(section),
        "course_title": section.curriculum_course.course.title or "",
        "faculty_label": _faculty_label(section.faculty),
        "roster_count": roster_count,
        "graded_count": graded_count,
        "pending_count": max(roster_count - graded_count, 0),
        "grade_entry_open": section.semester.status_id == "grade_entry",
        "detail_url": reverse("reg_class_roster_detail", args=[section.id]),
    }


def _registrar_breadcrumbs(label: str) -> list[BreadcrumbT]:
    """Return breadcrumbs rooted in the registrar workspace."""
    crumbs: list[BreadcrumbT] = [
        {
            "label": "Registrar dashboard",
            "href": reverse("staff_role_dashboard", args=["registrar"]),
        },
        {"label": "Class rosters", "href": reverse("reg_class_rosters")},
    ]
    if label:
        crumbs.append({"label": label, "href": ""})
    else:
        crumbs[-1]["href"] = ""
    return crumbs


def build_reg_class_roster_list_context(request: HttpRequest) -> PortalContextT:
    """Build the registrar class-roster list context."""
    user = cast(User, request.user)
    sidebar_role = registrar_sidebar_role(user)
    semester_param = request.GET.get("semester")
    semester_id = None if semester_param == "all" else clean_int(semester_param)
    selected_student_id = clean_int(request.GET.get("student_id"))
    selected_faculty_id = clean_int(request.GET.get("faculty_id"))
    sections = _filtered_sections(request.GET).order_by(
        "-semester__academic_year__start_date",
        "-semester__number",
        "curriculum_course__course__department__code",
        "curriculum_course__course__number",
        "number",
    )
    section_page = Paginator(sections, ROSTER_PAGE_SIZE).get_page(request.GET.get("page"))
    section_list = list(cast(list[Section], section_page.object_list))
    section_ids = [section.id for section in section_list]
    roster_counts, graded_counts = _section_counts(section_ids)
    rows = [
        _summary_row(section, roster_counts, graded_counts) for section in section_list
    ]
    pagination_query, pagination_hidden_fields = _pagination_hidden_fields(request.GET)
    return {
        "page_title": "Registrar class rosters",
        "page_summary": "Review section rosters by student, faculty, and semester.",
        "eyebrow": "Registrar officer",
        "sidebar_links": build_staff_sidebar_links(sidebar_role, "class_rosters"),
        "role_switcher": build_staff_role_switcher(user, "registrar"),
        "breadcrumbs": _registrar_breadcrumbs(""),
        "dashboard_url": reverse("staff_role_dashboard", args=["registrar"]),
        "student_autocomplete_url": reverse("reg_std_autocomplete"),
        "faculty_autocomplete_url": reverse("reg_faculty_autocomplete"),
        "semester_options": _semester_options(semester_id),
        "selected_student_id": selected_student_id,
        "selected_student_label": _student_filter_label(selected_student_id),
        "selected_faculty_id": selected_faculty_id,
        "selected_faculty_label": _faculty_filter_label(selected_faculty_id),
        "section_page": section_page,
        "section_rows": rows,
        "registrar_admin_links": _admin_shortcuts_for_models(
            user,
            REGISTRAR_ADMIN_SHORTCUTS,
        ),
        "pagination_query": pagination_query,
        "pagination_hidden_fields": pagination_hidden_fields,
        "pagination_action": request.path,
    }


def build_reg_class_roster_detail_context(
    request: HttpRequest,
    section_id: int,
) -> PortalContextT:
    """Build one registrar class-roster detail context."""
    user = cast(User, request.user)
    sidebar_role = registrar_sidebar_role(user)
    section = get_object_or_404(_base_section_queryset(), pk=section_id)
    registrations = list(
        Registration.objects.filter(section=section)
        .select_related("student__user", "status")
        .order_by("student__long_name", "student__student_id", "student_id")
    )
    student_ids = [registration.student_id for registration in registrations]
    grade_map = {
        grade.student_id: grade
        for grade in Grade.objects.filter(
            section=section,
            student_id__in=student_ids,
        ).select_related("value")
    }
    rows: list[RegistrarRosterStudentRowT] = []
    for registration in registrations:
        student = registration.student
        grade = grade_map.get(student.id)
        rows.append(
            {
                "student_label": _student_label(student),
                "student_id": student.student_id or str(student.id),
                "gender": _display_value(student.get_gender_display()),
                "age": _display_value(student.age),
                "registration_status": str(registration.status),
                "grade_code": grade.value.code.upper() if grade and grade.value else "",
                "grade_status": "Submitted" if grade and grade.value else "Pending",
            }
        )

    course_code = _course_code(section)
    return {
        "page_title": f"{course_code} class roster",
        "page_summary": "Read-only section roster for registrar review.",
        "eyebrow": "Registrar officer",
        "sidebar_links": build_staff_sidebar_links(sidebar_role, "class_rosters"),
        "role_switcher": build_staff_role_switcher(user, "registrar"),
        "breadcrumbs": _registrar_breadcrumbs(course_code),
        "dashboard_url": reverse("staff_role_dashboard", args=["registrar"]),
        "list_url": reverse("reg_class_rosters"),
        "section": section,
        "course_code": course_code,
        "course_title": section.curriculum_course.course.title or "",
        "faculty_label": _faculty_label(section.faculty),
        "grade_rows": rows,
    }


def registrar_faculty_results(query: str | None) -> list[AutocompleteResultT]:
    """Return faculty suggestions for registrar roster filtering."""
    clean_query = parse_str(query)
    if not clean_query:
        return []
    faculty_qs = (
        Faculty.objects.select_related(
            "staff_profile__user",
            "staff_profile__department",
            "college",
        )
        .filter(
            Q(staff_profile__long_name__icontains=clean_query)
            | Q(staff_profile__staff_id__icontains=clean_query)
            | Q(staff_profile__user__first_name__icontains=clean_query)
            | Q(staff_profile__user__last_name__icontains=clean_query)
            | Q(staff_profile__user__username__icontains=clean_query)
            | Q(staff_profile__department__code__icontains=clean_query)
            | Q(college__code__icontains=clean_query)
        )
        .order_by("staff_profile__long_name")[:15]
    )
    return [{"id": faculty.id, "text": _faculty_label(faculty)} for faculty in faculty_qs]


__all__ = [
    "build_reg_class_roster_detail_context",
    "build_reg_class_roster_list_context",
    "registrar_faculty_results",
]
