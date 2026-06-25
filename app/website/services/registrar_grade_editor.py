"""Registrar grade add/correction portal services."""

from __future__ import annotations

from typing import TypeAlias, TypedDict, cast

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpRequest, QueryDict
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone

from app.people.models.student import Student
from app.registry.models.grade import Grade
from app.registry.models.registration import Registration
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester
from app.website.services.grade_portal_common import (
    GradePortalError,
    grade_value_options,
    set_grade_code,
)
from app.website.services.portal_types import PortalContextT
from app.website.services.registrar_portal import (
    can_manage_registrar_grades,
    registrar_sidebar_role,
)
from app.website.services.staff_portal import (
    build_staff_role_switcher,
    build_staff_sidebar_links,
)

ContextT: TypeAlias = PortalContextT
GRADE_FIELD_PREFIX = "grade_section_"


class RegistrarGradeError(GradePortalError):
    """Raised when registrar grade correction data is unsafe or invalid."""


class RegistrarGradeEditorRowT(TypedDict):
    """One editable registrar grade row for a student section."""

    section: Section
    grade: Grade | None
    field_name: str
    course_code: str
    course_title: str
    credits: int
    faculty: str
    current_code: str
    source_label: str


def _require_registrar_grade_manager(user: User) -> None:
    """Raise unless the user may add and correct grades through the portal."""
    if not can_manage_registrar_grades(user):
        raise PermissionDenied("Registrar grade correction access is required.")


def _student_label(student: Student) -> str:
    """Return the preferred student label for registrar correction pages."""
    name = student.long_name or student.user.get_full_name() or student.username
    return f"{student.student_id or student.id} — {name}"


def _semester_label(semester: Semester) -> str:
    """Return the visible academic term label."""
    return f"{semester.academic_year.code} · Semester {semester.number}"


def _course_code(section: Section) -> str:
    """Return the course code shown in registrar grade rows."""
    course = section.curriculum_course.course
    return course.short_code or course.code or str(course)


def _faculty_label(section: Section) -> str:
    """Return the faculty label attached to a section."""
    if section.faculty and section.faculty.staff_profile:
        return section.faculty.staff_profile.user.get_full_name() or str(
            section.faculty.staff_profile
        )
    return "TBA"


def _credits(section: Section) -> int:
    """Return integer credit hours for the section."""
    return int(section.curriculum_course.credit_hours.code)


def _dashboard_url(student_id: int, semester_id: int) -> str:
    """Return the registrar dashboard filtered back to this student semester."""
    return f"{reverse('reg_grades_dashboard')}?student_id={student_id}&semester={semester_id}"


def _registered_section_ids(student: Student, semester: Semester) -> set[int]:
    """Return section ids where the student has a registration."""
    return set(
        Registration.objects.filter(
            student=student,
            section__semester=semester,
        ).values_list("section_id", flat=True)
    )


def _grade_by_section(student: Student, semester: Semester) -> dict[int, Grade]:
    """Return existing grades keyed by section id for the student semester."""
    grades = (
        Grade.objects.select_related("value", "section")
        .filter(student=student, section__semester=semester)
        .order_by("section_id")
    )
    return {grade.section_id: grade for grade in grades}


def _editor_sections(student: Student, semester: Semester) -> list[Section]:
    """Return registered and already-graded sections visible in the editor."""
    section_ids = _registered_section_ids(student, semester) | set(
        _grade_by_section(student, semester)
    )
    if not section_ids:
        return []
    return list(
        Section.objects.select_related(
            "semester__academic_year",
            "semester__status",
            "curriculum_course__course",
            "curriculum_course__credit_hours",
            "faculty__staff_profile__user",
        )
        .filter(id__in=section_ids)
        .order_by(
            "curriculum_course__course__short_code",
            "curriculum_course__course__code",
            "number",
            "id",
        )
    )


def build_registrar_grade_editor_rows(
    student: Student,
    semester: Semester,
) -> list[RegistrarGradeEditorRowT]:
    """Return editable rows for one student semester."""
    registered_section_ids = _registered_section_ids(student, semester)
    grade_by_section = _grade_by_section(student, semester)
    rows: list[RegistrarGradeEditorRowT] = []
    for section in _editor_sections(student, semester):
        grade = grade_by_section.get(section.id)
        course = section.curriculum_course.course
        source_label = "Registered"
        if section.id not in registered_section_ids:
            source_label = "Historical grade only"
        rows.append(
            {
                "section": section,
                "grade": grade,
                "field_name": f"{GRADE_FIELD_PREFIX}{section.id}",
                "course_code": _course_code(section),
                "course_title": course.title or "",
                "credits": _credits(section),
                "faculty": _faculty_label(section),
                "current_code": grade.value.code if grade and grade.value else "",
                "source_label": source_label,
            }
        )
    return rows


def build_registrar_grade_editor_context(
    request: HttpRequest,
    student_id: int,
    semester_id: int,
) -> ContextT:
    """Build context for the registrar grade add/correction form."""
    user = cast(User, request.user)
    _require_registrar_grade_manager(user)
    student = get_object_or_404(Student.objects.select_related("user"), pk=student_id)
    semester = get_object_or_404(
        Semester.objects.select_related("academic_year", "status"),
        pk=semester_id,
    )
    sidebar_role = registrar_sidebar_role(user)
    return {
        "page_title": "Add or correct grades",
        "page_summary": "Registrar override for official student grade records.",
        "eyebrow": "Registrar",
        "sidebar_links": build_staff_sidebar_links(sidebar_role, "grades"),
        "role_switcher": build_staff_role_switcher(user, "registrar"),
        "breadcrumbs": [
            {
                "label": "Registrar dashboard",
                "href": reverse("staff_role_dashboard", args=["registrar"]),
            },
            {"label": "Grade review", "href": reverse("reg_grades_dashboard")},
            {"label": "Grade correction", "href": ""},
        ],
        "student": student,
        "student_label": _student_label(student),
        "semester": semester,
        "semester_label": _semester_label(semester),
        "semester_status": semester.status.label if semester.status else "Not set",
        "grade_rows": build_registrar_grade_editor_rows(student, semester),
        "grade_values": grade_value_options(),
        "dashboard_url": _dashboard_url(student.id, semester.id),
        "save_url": reverse("reg_grade_semester_editor", args=[student.id, semester.id]),
    }


def _posted_section_ids(data: QueryDict) -> set[int]:
    """Return section ids submitted through registrar grade fields."""
    section_ids: set[int] = set()
    for key in data.keys():
        if not key.startswith(GRADE_FIELD_PREFIX):
            continue
        raw_section_id = key.removeprefix(GRADE_FIELD_PREFIX)
        try:
            section_ids.add(int(raw_section_id))
        except ValueError as exc:
            raise RegistrarGradeError("Invalid grade section field.") from exc
    return section_ids


def _append_registrar_note(grade: Grade, user: User) -> None:
    """Append a compact registrar correction note to the grade row."""
    timestamp = timezone.now().replace(microsecond=0).isoformat()
    note = f"[{timestamp}] Registrar portal update by {user.username}."
    grade.info = f"{grade.info.rstrip()}\n{note}".strip()
    grade.save(update_fields=["info"], recompute_effective=False)


def save_registrar_grade_editor(
    user: User,
    student_id: int,
    semester_id: int,
    data: QueryDict,
) -> int:
    """Save registrar grade additions/corrections for one student semester."""
    _require_registrar_grade_manager(user)
    student = get_object_or_404(Student, pk=student_id)
    semester = get_object_or_404(Semester, pk=semester_id)
    rows = build_registrar_grade_editor_rows(student, semester)
    row_by_section_id = {row["section"].id: row for row in rows}
    unknown_section_ids = _posted_section_ids(data) - set(row_by_section_id)
    if unknown_section_ids:
        raise RegistrarGradeError(
            "One submitted grade row is not part of this student semester."
        )

    changed = 0
    with transaction.atomic():
        for row in rows:
            field_name = row["field_name"]
            if field_name not in data:
                continue
            grade_code = data.get(field_name, "")
            grade = row["grade"]
            if grade is None:
                if not grade_code.strip():
                    continue
                # Missing rows are created only on POST, never when opening the form.
                grade = Grade.objects.create(
                    student=student,
                    section=row["section"],
                )
            if set_grade_code(grade, grade_code, error_type=RegistrarGradeError):
                _append_registrar_note(grade, user)
                changed += 1
    return changed


__all__ = [
    "RegistrarGradeEditorRowT",
    "RegistrarGradeError",
    "build_registrar_grade_editor_context",
    "build_registrar_grade_editor_rows",
    "save_registrar_grade_editor",
]
