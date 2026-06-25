"""Faculty grade-entry portal services."""

from __future__ import annotations

from typing import TypeAlias, cast

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import QuerySet
from django.http import HttpRequest, QueryDict
from django.shortcuts import get_object_or_404
from django.urls import reverse

from app.people.models.faculty import Faculty
from app.registry.models.grade import Grade, GradeValue
from app.registry.models.registration import Registration
from app.timetable.models.section import Section
from app.website.services.faculty_grade_types import (
    FacultyGradeRowT,
    FacultySectionRowT,
)
from app.website.services.grade_portal_common import (
    GradePortalError,
    grade_value_for_code,
    grade_value_options,
    set_grade_code,
)
from app.website.services.portal_types import AdminShortcutT, PortalContextT
from app.website.services.staff_common import (
    admin_shortcuts_for_models,
    get_faculty_profile,
)
from app.website.services.staff_portal import (
    build_staff_role_switcher,
    build_staff_sidebar_links,
)

GRADE_ENTRY_STATUS = "grade_entry"

SectionQueryT: TypeAlias = QuerySet[Section]


class FacultyGradeError(GradePortalError):
    """Raised when a faculty grade action cannot be applied safely."""


def _faculty_admin_links(user: User) -> list[AdminShortcutT]:
    """Return admin shortcuts relevant to faculty grade maintenance."""
    return admin_shortcuts_for_models(
        user,
        (
            ("My sections", Section),
            ("My grades", Grade),
        ),
    )


def require_faculty_profile(user: User) -> Faculty:
    """Return the faculty profile or deny the workflow."""
    faculty = get_faculty_profile(user)
    if faculty is None:
        raise PermissionDenied("A faculty profile is required for grade entry.")
    return faculty


def grade_entry_open(section: Section) -> bool:
    """Return whether grade mutations are allowed for this section."""
    return section.semester.status_id == GRADE_ENTRY_STATUS


def assigned_sections_for_faculty(faculty: Faculty) -> SectionQueryT:
    """Return the sections assigned to a faculty member."""
    return Section.objects.filter(faculty=faculty).select_related(
        "semester__academic_year",
        "semester__status",
        "curriculum_course__course",
        "curriculum_course__credit_hours",
    )


def get_faculty_section_or_404(user: User, section_id: int) -> Section:
    """Return an assigned section or raise 404 to avoid leaking section ids."""
    faculty = require_faculty_profile(user)
    return get_object_or_404(assigned_sections_for_faculty(faculty), pk=section_id)


def course_code(section: Section) -> str:
    """Return the most familiar course code for a section."""
    course = section.curriculum_course.course
    return course.short_code or course.code or str(course)


def ensure_grade_roster(section: Section) -> list[Grade]:
    """Ensure every registered student in a section has one editable grade row."""
    registrations = (
        Registration.objects.filter(section=section)
        .select_related("student__user")
        .order_by("student__long_name", "student__student_id", "student_id")
    )
    grades: list[Grade] = []
    for registration in registrations:
        grade, _created = Grade.objects.get_or_create(
            student=registration.student,
            section=section,
        )
        grades.append(grade)
    return grades


def build_faculty_grade_rows(section: Section) -> list[FacultyGradeRowT]:
    """Return display rows for one section roster."""
    grades = ensure_grade_roster(section)
    grade_ids = [grade.id for grade in grades]
    hydrated = (
        Grade.objects.select_related("student__user", "value")
        .filter(id__in=grade_ids)
        .order_by("student__long_name", "student__student_id", "student_id")
    )
    return [
        {
            "grade": grade,
            "student": grade.student,
            "student_label": grade.student.long_name
            or grade.student.user.get_full_name()
            or grade.student.user.username,
            "student_id": grade.student.student_id or str(grade.student_id),
            "current_code": grade.value.code if grade.value else "",
        }
        for grade in hydrated
    ]


def _section_counts(section_ids: list[int]) -> tuple[dict[int, int], dict[int, int]]:
    """Return roster and graded counts keyed by section id."""
    roster_counts: dict[int, int] = {}
    for section_id in Registration.objects.filter(section_id__in=section_ids).values_list(
        "section_id", flat=True
    ):
        key = int(section_id)
        roster_counts[key] = roster_counts.get(key, 0) + 1

    graded_counts: dict[int, int] = {}
    for section_id in Grade.objects.filter(
        section_id__in=section_ids,
        value__isnull=False,
    ).values_list("section_id", flat=True):
        key = int(section_id)
        graded_counts[key] = graded_counts.get(key, 0) + 1
    return roster_counts, graded_counts


def build_faculty_grade_sections_context(request: HttpRequest) -> PortalContextT:
    """Build the faculty section list for grade entry."""
    user = cast(User, request.user)
    faculty = require_faculty_profile(user)
    sections = list(
        assigned_sections_for_faculty(faculty).order_by(
            "-semester__start_date",
            "-semester__number",
            "curriculum_course__course__short_code",
            "number",
        )
    )
    roster_counts, graded_counts = _section_counts([section.id for section in sections])
    section_rows: list[FacultySectionRowT] = []
    for section in sections:
        roster_count = roster_counts.get(section.id, 0)
        graded_count = graded_counts.get(section.id, 0)
        section_rows.append(
            {
                "section": section,
                "course_code": course_code(section),
                "course_title": section.curriculum_course.course.title or "",
                "roster_count": roster_count,
                "pending_count": max(roster_count - graded_count, 0),
                "grade_entry_open": grade_entry_open(section),
                "roster_url": reverse("faculty_grade_roster", args=[section.id]),
                "download_url": reverse(
                    "faculty_grade_roster_download",
                    args=[section.id],
                ),
            }
        )
    return {
        "page_title": "Faculty grades",
        "page_summary": (
            "Enter section grades while the registrar grade-entry period is open."
        ),
        "eyebrow": "Faculty",
        "sidebar_links": build_staff_sidebar_links("faculty", "faculty_grades"),
        "role_switcher": build_staff_role_switcher(user, "faculty"),
        "breadcrumbs": [
            {
                "label": "Faculty dashboard",
                "href": reverse("staff_role_dashboard", args=["faculty"]),
            },
            {"label": "Grade entry", "href": ""},
        ],
        "section_rows": section_rows,
        "dashboard_url": reverse("staff_role_dashboard", args=["faculty"]),
        "faculty_admin_links": _faculty_admin_links(user),
    }


def build_faculty_grade_roster_context(
    request: HttpRequest,
    section_id: int,
) -> PortalContextT:
    """Build one editable faculty grade roster."""
    user = cast(User, request.user)
    section = get_faculty_section_or_404(user, section_id)
    return {
        "page_title": f"Grade roster · {course_code(section)}",
        "page_summary": "Save grades explicitly or let Tusis autosave changed fields.",
        "eyebrow": "Faculty",
        "sidebar_links": build_staff_sidebar_links("faculty", "faculty_grades"),
        "role_switcher": build_staff_role_switcher(user, "faculty"),
        "breadcrumbs": [
            {
                "label": "Faculty dashboard",
                "href": reverse("staff_role_dashboard", args=["faculty"]),
            },
            {"label": "Grade entry", "href": reverse("faculty_grade_sections")},
            {"label": course_code(section), "href": ""},
        ],
        "section": section,
        "course_code": course_code(section),
        "course_title": section.curriculum_course.course.title or "",
        "grade_entry_open": grade_entry_open(section),
        "grade_rows": build_faculty_grade_rows(section),
        "grade_values": grade_value_options(),
        "dashboard_url": reverse("staff_role_dashboard", args=["faculty"]),
        "sections_url": reverse("faculty_grade_sections"),
        "download_url": reverse("faculty_grade_roster_download", args=[section.id]),
        "upload_url": reverse("faculty_grade_roster_upload", args=[section.id]),
        "autosave_url": reverse("faculty_grade_roster_autosave", args=[section.id]),
        "faculty_admin_links": _faculty_admin_links(user),
    }


def _grade_value_for_code(grade_code: str) -> GradeValue | None:
    """Return a grade value for a submitted code, or None for a blank grade."""
    return grade_value_for_code(grade_code, error_type=FacultyGradeError)


def _set_grade_code(grade: Grade, grade_code: str) -> bool:
    """Set one grade code and return whether it changed."""
    return set_grade_code(grade, grade_code, error_type=FacultyGradeError)


def save_grade_roster(section: Section, data: QueryDict) -> int:
    """Save all posted grade fields for an open faculty roster."""
    if not grade_entry_open(section):
        raise FacultyGradeError("Grade entry is closed for this section.")
    changed = 0
    with transaction.atomic():
        for grade in build_faculty_grade_rows(section):
            field_name = f"grade_{grade['grade'].id}"
            if field_name in data and _set_grade_code(
                grade["grade"],
                data.get(field_name, ""),
            ):
                changed += 1
    return changed


def save_grade_autosave(
    user: User,
    section_id: int,
    grade_id: int,
    grade_code: str,
) -> Grade:
    """Save one changed grade field for the faculty autosave endpoint."""
    section = get_faculty_section_or_404(user, section_id)
    if not grade_entry_open(section):
        raise FacultyGradeError("Grade entry is closed for this section.")
    grade = get_object_or_404(
        Grade.objects.select_related("value"),
        pk=grade_id,
        section=section,
    )
    _set_grade_code(grade, grade_code)
    grade.refresh_from_db()
    return grade
