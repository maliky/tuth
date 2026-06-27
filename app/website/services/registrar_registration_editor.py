"""Registrar registration add/change/delete portal services."""

from __future__ import annotations

from typing import TypeAlias, TypedDict, cast

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q, QuerySet
from django.http import HttpRequest, QueryDict
from django.shortcuts import get_object_or_404
from django.urls import reverse

from app.finance.models.invoice import CrsInvoice
from app.finance.models.payment import Payment
from app.people.models.student import Student
from app.registry.models.grade import Grade
from app.registry.models.registration import Registration
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester
from app.website.services.portal_types import PortalContextT
from app.website.services.registrar_portal import (
    can_manage_registrar_registrations,
    clean_int,
    registrar_sidebar_role,
)
from app.website.services.staff_portal import (
    build_staff_role_switcher,
    build_staff_sidebar_links,
)

ContextT: TypeAlias = PortalContextT


class RegistrarRegistrationError(ValueError):
    """Raised when registrar registration correction data is unsafe or invalid."""


class SectionAutocompleteResultT(TypedDict):
    """Select2-compatible section result for registrar registration correction."""

    id: int
    text: str


class RegistrarRegistrationRowT(TypedDict):
    """One registration row rendered in the registrar correction form."""

    registration: Registration
    course_code: str
    course_title: str
    section_label: str
    status_label: str
    block_reason: str
    can_move: bool
    can_delete: bool


def _require_registrar_registration_viewer(user: User) -> None:
    """Raise unless the user may open registrar registration correction pages."""
    if not can_manage_registrar_registrations(user):
        raise PermissionDenied("Registrar registration access is required.")


def _require_perm(user: User, permission: str, message: str) -> None:
    """Raise a permission error for a missing model-level action right."""
    if not user.has_perm(permission):
        raise PermissionDenied(message)


def _student_label(student: Student) -> str:
    """Return the preferred student label for registrar correction pages."""
    name = student.long_name or student.user.get_full_name() or student.username
    return f"{student.student_id or student.id} — {name}"


def _semester_label(semester: Semester) -> str:
    """Return the visible academic term label."""
    return f"{semester.academic_year.code} · Semester {semester.number}"


def _course_code(section: Section) -> str:
    """Return the course code shown in registrar registration rows."""
    course = section.curriculum_course.course
    return course.short_code or course.code or str(course)


def _section_label(section: Section) -> str:
    """Return a compact section label without triggering room lookups."""
    return f"{_course_code(section)}:s{section.number}"


def _section_text(section: Section) -> str:
    """Return the label used by the section autocomplete."""
    curriculum = section.curriculum_course.curriculum
    course = section.curriculum_course.course
    return (
        f"{_section_label(section)} — {course.title or 'Untitled'}"
        f" — {curriculum.short_name}"
    )


def _registration_qs() -> QuerySet[Registration]:
    """Return registrations with related records needed by the editor."""
    return Registration.objects.select_related(
        "student__user",
        "section__semester__academic_year",
        "section__curriculum_course__course",
        "section__curriculum_course__curriculum",
        "status",
    )


def _registrations_for_student_semester(
    student: Student,
    semester: Semester,
) -> QuerySet[Registration]:
    """Return registrations for one student semester."""
    return _registration_qs().filter(student=student, section__semester=semester)


def _registration_for_student_semester(
    student: Student,
    semester: Semester,
    registration_id: int | None,
) -> Registration:
    """Return a registration row scoped to the selected student semester."""
    if registration_id is None:
        raise RegistrarRegistrationError("Select a registration.")
    registration = (
        _registrations_for_student_semester(student, semester)
        .filter(pk=registration_id)
        .first()
    )
    if registration is None:
        raise RegistrarRegistrationError("Registration not found for this student term.")
    return registration


def _invoice_qs(student: Student, section: Section) -> QuerySet[CrsInvoice]:
    """Return course invoices matching a registration identity."""
    return CrsInvoice.objects.filter(
        student=student,
        curriculum_course=section.curriculum_course,
        semester=section.semester,
    )


def _finance_parent_ids(student: Student, section: Section) -> list[int]:
    """Return parent invoice ids linked to matching course invoices."""
    parent_ids = _invoice_qs(student, section).values_list(
        "student_semester_invoice_id",
        flat=True,
    )
    return [int(value) for value in parent_ids if value]


def _registration_blockers(registration: Registration) -> list[str]:
    """Return reasons a registration cannot be moved or deleted safely."""
    blockers: list[str] = []
    if registration.status_id != "pending":
        blockers.append("status is not pending")
    if Grade.objects.filter(
        student=registration.student,
        section=registration.section,
    ).exists():
        blockers.append("grade exists")
    if _invoice_qs(registration.student, registration.section).exists():
        blockers.append("course invoice exists")
    parent_ids = _finance_parent_ids(registration.student, registration.section)
    if (
        parent_ids
        and Payment.objects.filter(student_semester_invoice_id__in=parent_ids).exists()
    ):
        blockers.append("payment history exists")
    return blockers


def _section_qs(semester: Semester) -> QuerySet[Section]:
    """Return sections eligible for registrar selection in one semester."""
    return Section.objects.select_related(
        "semester__academic_year",
        "curriculum_course__course",
        "curriculum_course__curriculum",
    ).filter(semester=semester)


def _target_section(semester: Semester, section_id: int | None) -> Section:
    """Return the selected section, enforcing same-semester correction."""
    if section_id is None:
        raise RegistrarRegistrationError("Select a section.")
    section = _section_qs(semester).filter(pk=section_id).first()
    if section is None:
        raise RegistrarRegistrationError("Select a section from the same semester.")
    return section


def _ensure_new_registration_target(student: Student, section: Section) -> None:
    """Raise when creating or moving would collide with existing records."""
    if Registration.objects.filter(student=student, section=section).exists():
        raise RegistrarRegistrationError("The student already has that registration.")
    if _invoice_qs(student, section).exists():
        raise RegistrarRegistrationError(
            "A course invoice already exists for the target section."
        )


def _add_registration(
    user: User, student: Student, semester: Semester, data: QueryDict
) -> str:
    """Create one pending registration for the selected student semester."""
    _require_perm(
        user, "registry.add_registration", "Add registration access is required."
    )
    section = _target_section(semester, clean_int(data.get("section_id")))
    _ensure_new_registration_target(student, section)
    Registration.objects.create(student=student, section=section)
    return f"Added {_section_label(section)}."


def _move_registration(
    user: User,
    student: Student,
    semester: Semester,
    data: QueryDict,
) -> str:
    """Move one clean pending registration to another same-semester section."""
    _require_perm(
        user,
        "registry.change_registration",
        "Change registration access is required.",
    )
    registration = _registration_for_student_semester(
        student,
        semester,
        clean_int(data.get("registration_id")),
    )
    blockers = _registration_blockers(registration)
    if blockers:
        raise RegistrarRegistrationError(
            f"Registration cannot be moved: {', '.join(blockers)}."
        )
    section = _target_section(semester, clean_int(data.get("section_id")))
    if registration.section_id == section.id:
        return "Registration already uses that section."
    _ensure_new_registration_target(student, section)
    registration.section = section
    registration.save(update_fields=["section"])
    return f"Moved registration to {_section_label(section)}."


def _delete_registration(
    user: User,
    student: Student,
    semester: Semester,
    data: QueryDict,
) -> str:
    """Delete one clean pending registration."""
    _require_perm(
        user,
        "registry.delete_registration",
        "Delete registration access is required.",
    )
    registration = _registration_for_student_semester(
        student,
        semester,
        clean_int(data.get("registration_id")),
    )
    blockers = _registration_blockers(registration)
    if blockers:
        raise RegistrarRegistrationError(
            f"Registration cannot be deleted: {', '.join(blockers)}."
        )
    section_label = _section_label(registration.section)
    registration.delete()
    return f"Deleted {section_label}."


def save_registrar_registration_editor(
    user: User,
    student_id: int,
    semester_id: int,
    data: QueryDict,
) -> str:
    """Save one registrar registration correction action."""
    _require_registrar_registration_viewer(user)
    student = get_object_or_404(Student.objects.select_related("user"), pk=student_id)
    semester = get_object_or_404(Semester, pk=semester_id)
    action = data.get("action", "")
    with transaction.atomic():
        if action == "add_registration":
            return _add_registration(user, student, semester, data)
        if action == "move_registration":
            return _move_registration(user, student, semester, data)
        if action == "delete_registration":
            return _delete_registration(user, student, semester, data)
    raise RegistrarRegistrationError("Unknown registration action.")


def build_registrar_registration_rows(
    student: Student,
    semester: Semester,
    user: User,
) -> list[RegistrarRegistrationRowT]:
    """Return registration rows for one student semester."""
    can_change = user.has_perm("registry.change_registration")
    can_delete = user.has_perm("registry.delete_registration")
    rows: list[RegistrarRegistrationRowT] = []
    for registration in _registrations_for_student_semester(student, semester):
        blockers = _registration_blockers(registration)
        course = registration.section.curriculum_course.course
        rows.append(
            {
                "registration": registration,
                "course_code": _course_code(registration.section),
                "course_title": course.title or "",
                "section_label": _section_label(registration.section),
                "status_label": str(registration.status),
                "block_reason": ", ".join(blockers),
                "can_move": can_change and not blockers,
                "can_delete": can_delete and not blockers,
            }
        )
    return rows


def build_registrar_registration_editor_context(
    request: HttpRequest,
    student_id: int,
    semester_id: int,
) -> ContextT:
    """Build context for the registrar registration correction form."""
    user = cast(User, request.user)
    _require_registrar_registration_viewer(user)
    student = get_object_or_404(Student.objects.select_related("user"), pk=student_id)
    semester = get_object_or_404(
        Semester.objects.select_related("academic_year", "status"),
        pk=semester_id,
    )
    sidebar_role = registrar_sidebar_role(user)
    return {
        "page_title": "Correct registrations",
        "page_summary": "Registrar corrections for student course registrations.",
        "eyebrow": "Registrar",
        "sidebar_links": build_staff_sidebar_links(sidebar_role, "grades"),
        "role_switcher": build_staff_role_switcher(user, "registrar"),
        "breadcrumbs": [
            {
                "label": "Registrar dashboard",
                "href": reverse("staff_role_dashboard", args=["registrar"]),
            },
            {"label": "Grade review", "href": reverse("reg_grades_dashboard")},
            {"label": "Registration correction", "href": ""},
        ],
        "student": student,
        "student_label": _student_label(student),
        "semester": semester,
        "semester_label": _semester_label(semester),
        "semester_status": semester.status.label if semester.status else "Not set",
        "registration_rows": build_registrar_registration_rows(
            student,
            semester,
            user,
        ),
        "can_add_registration": user.has_perm("registry.add_registration"),
        "section_autocomplete_url": reverse(
            "reg_registration_section_autocomplete",
            args=[semester.id],
        ),
        "dashboard_url": (
            f"{reverse('reg_grades_dashboard')}?student_id={student.id}"
            f"&semester={semester.id}"
        ),
        "grade_editor_url": reverse(
            "reg_grade_semester_editor",
            args=[student.id, semester.id],
        ),
        "save_url": reverse(
            "reg_registration_semester_editor",
            args=[student.id, semester.id],
        ),
    }


def registrar_section_results(
    user: User,
    semester_id: int,
    query: str | None,
) -> list[SectionAutocompleteResultT]:
    """Return section suggestions scoped to one registrar correction semester."""
    _require_registrar_registration_viewer(user)
    clean_query = (query or "").strip()
    if not clean_query:
        return []
    semester = get_object_or_404(Semester, pk=semester_id)
    qs = _section_qs(semester)
    number = clean_int(clean_query)
    search_filter = (
        Q(curriculum_course__course__short_code__icontains=clean_query)
        | Q(curriculum_course__course__code__icontains=clean_query)
        | Q(curriculum_course__course__title__icontains=clean_query)
        | Q(curriculum_course__curriculum__short_name__icontains=clean_query)
        | Q(curriculum_course__curriculum__long_name__icontains=clean_query)
    )
    if number is not None:
        search_filter |= Q(number=number)
    sections = qs.filter(search_filter).order_by(
        "curriculum_course__course__short_code",
        "number",
    )[:20]
    return [{"id": section.id, "text": _section_text(section)} for section in sections]


__all__ = [
    "RegistrarRegistrationError",
    "RegistrarRegistrationRowT",
    "SectionAutocompleteResultT",
    "build_registrar_registration_editor_context",
    "build_registrar_registration_rows",
    "registrar_section_results",
    "save_registrar_registration_editor",
]
