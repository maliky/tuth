"""Typed services for registrar-facing portal views."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date
from typing import TypeAlias, TypedDict, cast
from urllib.parse import urlencode

from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone

from app.people.models.student import Student
from app.registry.gpa import get_grade_points_and_credits
from app.registry.models.grade import Grade
from app.registry.models.registration import Registration
from app.shared.auth.perms import UserRole
from app.shared.utils import parse_str
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester, SemesterStatus
from app.website.services.portal_types import PortalContextT
from app.website.services.staff_portal import (
    build_staff_role_switcher,
    build_staff_sidebar_links,
)
from app.website.services.staff_common import _admin_shortcuts_for_models
from app.website.services.staff_contexts import REGISTRAR_ADMIN_SHORTCUTS
from app.website.services.transcript_document import (
    build_transcript_document,
    flatten_transcript_rows,
)

ContextT: TypeAlias = PortalContextT
SemesterWindowSortKeyT: TypeAlias = tuple[int, int, date, date, int, int]
REGISTRAR_GRADE_ROLE_LABELS = frozenset(
    {
        UserRole.REGISTRAR.value.label,
        UserRole.REGISTRAR_OFFICER.value.label,
    }
)


class RegGradeRowT(TypedDict):
    """Details for a registrar grade row."""

    course_code: str
    course_title: str
    credits: int
    grade: str
    faculty: str
    roster_url: str
    is_missing_grade: bool


class RegSemGpT(TypedDict):
    """Grouped grade rows for a semester."""

    semester: Semester
    label: str
    rows: list[RegGradeRowT]
    credits_total: int
    gpa: str
    grade_editor_url: str
    can_manage_grades: bool


class RegStdGpT(TypedDict):
    """Grouped grade rows for a student."""

    student: Student
    std_label: str
    student_id: str
    semesters: list[RegSemGpT]
    credits_total: int
    gpa: str


class RegSnapshotFactT(TypedDict):
    """One fact displayed in the registrar selected-student snapshot."""

    label: str
    value: str


class RegStudentSnapshotT(TypedDict):
    """Academic summary shown when Registrar filters by one student."""

    name: str
    student_id: str
    rows: list[RegSnapshotFactT]
    transcript_url: str
    rosters_url: str


class RegSemesterWindowGroupT(TypedDict):
    """Grouped semester-window rows for the registrar portal."""

    academic_year: str
    is_current_academic_year: bool
    semesters: list[Semester]


class StudentAutocompleteResultT(TypedDict):
    """Select2-compatible student autocomplete result."""

    id: int
    text: str


class SemesterOptionT(TypedDict):
    """Portal semester filter option for registrar views."""

    value: str
    label: str
    selected: bool


def clean_int(value: str | None) -> int | None:
    """Return a cleaned integer or None."""
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def user_has_registrar_grade_role(user: User) -> bool:
    """Return whether the user is a registrar actor for grade workflows."""
    return (
        user.is_superuser
        or user.groups.filter(name__in=REGISTRAR_GRADE_ROLE_LABELS).exists()
    )


def can_manage_registrar_grades(user: User) -> bool:
    """Return whether a user can add or correct grades through the portal."""
    return user_has_registrar_grade_role(user) and all(
        user.has_perm(permission)
        for permission in (
            "registry.view_grade",
            "registry.add_grade",
            "registry.change_grade",
        )
    )


def latest_graded_sem_id() -> int | None:
    """Return the most recent semester id that has at least one grade."""
    return (
        Grade.objects.order_by(
            "-section__semester__start_date",
            "-section__semester__number",
            "-section__semester_id",
        )
        .values_list("section__semester_id", flat=True)
        .first()
    )


def group_semester_windows(
    semesters: Sequence[Semester],
    *,
    current_academic_year_id: int | None = None,
) -> list[RegSemesterWindowGroupT]:
    """Group semester windows by academic year, current year first."""
    semester_list = list(semesters)
    active_year_id = current_academic_year_id
    if active_year_id is None:
        active_year_id = current_academic_year_id_for_windows(semester_list)
    groups: list[RegSemesterWindowGroupT] = []
    group_lookup: dict[str, RegSemesterWindowGroupT] = {}
    sorted_semesters = sorted(
        semester_list,
        key=lambda semester: semester_window_sort_key(semester, active_year_id),
        reverse=True,
    )
    for semester in sorted_semesters:
        label = semester.academic_year.code
        group = group_lookup.get(label)
        if group is None:
            group = {
                "academic_year": label,
                "is_current_academic_year": semester.academic_year_id == active_year_id,
                "semesters": [],
            }
            group_lookup[label] = group
            groups.append(group)
        group["semesters"].append(semester)
    return groups


def current_academic_year_id_for_windows(
    semesters: Sequence[Semester],
    today: date | None = None,
) -> int | None:
    """Return the academic year that should anchor registrar windows."""
    ref_date = today or timezone.localdate()
    current_semesters = [
        semester for semester in semesters if semester_contains_date(semester, ref_date)
    ]
    if current_semesters:
        current_semester = max(
            current_semesters,
            key=lambda semester: (
                semester_start_date(semester),
                semester.number,
                semester.id,
            ),
        )
        return current_semester.academic_year_id

    current_year_semesters = [
        semester
        for semester in semesters
        if semester.academic_year.start_date
        <= ref_date
        <= semester.academic_year.end_date
    ]
    if current_year_semesters:
        return current_year_semesters[0].academic_year_id
    return None


def semester_contains_date(semester: Semester, ref_date: date) -> bool:
    """Return whether a semester's recorded date range contains ref_date."""
    semester_end = semester.end_date or semester.academic_year.end_date
    return semester_start_date(semester) <= ref_date <= semester_end


def semester_start_date(semester: Semester) -> date:
    """Return the most reliable start date available for a semester."""
    return semester.start_date or semester.academic_year.start_date


def semester_window_sort_key(
    semester: Semester,
    current_academic_year_id: int | None = None,
) -> SemesterWindowSortKeyT:
    """Return the registrar display key for course-window semesters."""
    # The current year is the navigation anchor; this keeps noisy future imports below it.
    current_year = (
        current_academic_year_id is not None
        and semester.academic_year_id == current_academic_year_id
    )
    return (
        1 if current_year else 0,
        1 if semester.is_regio_open() else 0,
        semester_start_date(semester),
        semester.academic_year.start_date,
        semester.number,
        semester.id,
    )


def registrar_student_results(query: str | None) -> list[StudentAutocompleteResultT]:
    """Return student suggestions for the registrar grade dashboard."""
    clean_query = parse_str(query)
    if not clean_query:
        return []
    students = (
        Student.objects.select_related("user")
        .filter(
            Q(student_id__icontains=clean_query)
            | Q(long_name__icontains=clean_query)
            | Q(user__first_name__icontains=clean_query)
            | Q(user__last_name__icontains=clean_query)
            | Q(user__username__icontains=clean_query)
        )
        .order_by("long_name")[:15]
    )
    return [
        {
            "id": student.id,
            "text": f"{student.student_id} — {student.long_name}",
        }
        for student in students
    ]


def _display_value(value: object) -> str:
    """Return a stable display value for registrar snapshot rows."""
    if value is None:
        return "Not set"
    text = str(value).strip()
    return text or "Not set"


def _student_display_name(student: Student) -> str:
    """Return the best available student display name."""
    return student.long_name or student.user.get_full_name() or student.username


def _student_label(student: Student) -> str:
    """Return the student selector label used across registrar pages."""
    return f"{student.student_id} — {_student_display_name(student)}"


def registrar_sidebar_role(user: User) -> str:
    """Return the registrar sidebar role matching the user's staff group."""
    if user.groups.filter(name=UserRole.REGISTRAR_OFFICER.value.label).exists():
        return "reg_officer"
    return "registrar"


def _roster_list_url(student_id: int, semester_param: str | None) -> str:
    """Return the registrar roster list URL filtered to a student."""
    params = {"student_id": str(student_id), "semester": semester_param or "all"}
    return f"{reverse('reg_class_rosters')}?{urlencode(params)}"


def build_reg_student_snapshot(
    student: Student,
    semester_param: str | None,
) -> RegStudentSnapshotT:
    """Return the selected-student summary for the registrar grades dashboard."""
    curriculum = student.primary_curriculum
    grade_count = Grade.objects.filter(student=student).count()
    registration_count = Registration.objects.filter(student=student).count()
    return {
        "name": _student_display_name(student),
        "student_id": student.student_id or str(student.id),
        "rows": [
            {"label": "Username", "value": _display_value(student.username)},
            {"label": "Program", "value": _display_value(curriculum.short_name)},
            {"label": "College", "value": _display_value(curriculum.college)},
            {
                "label": "Entry semester",
                "value": _display_value(student.entry_semester),
            },
            {
                "label": "Current semester",
                "value": _display_value(student.last_enrolled_semester),
            },
            {"label": "Class level", "value": _display_value(student.class_level)},
            {
                "label": "Completed credits",
                "value": _display_value(student.completed_credits),
            },
            {"label": "Max credits", "value": _display_value(student.max_credit_hours)},
            {"label": "Grade rows", "value": _display_value(grade_count)},
            {"label": "Registrations", "value": _display_value(registration_count)},
        ],
        "transcript_url": reverse("reg_grade_transcript", args=[student.id]),
        "rosters_url": _roster_list_url(student.id, semester_param),
    }


def _semester_options(
    semester_id: int | None, all_selected: bool
) -> list[SemesterOptionT]:
    """Build semester filter options for registrar pages."""
    options: list[SemesterOptionT] = [
        {"value": "all", "label": "All semesters", "selected": all_selected}
    ]
    for sem in Semester.objects.select_related("academic_year").order_by(
        "-academic_year__start_date",
        "-number",
    ):
        options.append(
            {
                "value": str(sem.id),
                "label": f"{sem.academic_year.code} · Semester {sem.number}",
                "selected": semester_id == sem.id,
            }
        )
    return options


def _pagination_hidden_fields(request: HttpRequest) -> tuple[str, list[dict[str, str]]]:
    """Return encoded query and hidden fields preserving current filters."""
    pagination_params = request.GET.copy()
    pagination_params.pop("page", None)
    hidden_fields: list[dict[str, str]] = []
    for key, values in pagination_params.lists():
        for value in values:
            hidden_fields.append({"name": key, "value": value})
    return pagination_params.urlencode(), hidden_fields


def build_reg_grades_context(request: HttpRequest) -> ContextT:
    """Build context for the registrar grade dashboard."""
    user = cast(User, request.user)
    sidebar_role = registrar_sidebar_role(user)
    can_manage_grades = can_manage_registrar_grades(user)
    selected_student_id = clean_int(request.GET.get("student_id"))
    semester_param = request.GET.get("semester")
    semester_id = clean_int(semester_param)
    semester_param_present = "semester" in request.GET
    if semester_param == "all" or not semester_param_present:
        semester_id = None

    if selected_student_id:
        students_qs = Student.objects.filter(id=selected_student_id).select_related(
            "user"
        )
        if semester_id:
            students_qs = students_qs.filter(
                Q(grade__section__semester_id=semester_id)
                | Q(student_registrations__section__semester_id=semester_id)
            )
        else:
            students_qs = students_qs.filter(
                Q(grade__isnull=False) | Q(student_registrations__isnull=False)
            )
    else:
        students_qs = Student.objects.filter(grade__isnull=False).select_related("user")
        if semester_id:
            students_qs = students_qs.filter(grade__section__semester_id=semester_id)
    students_qs = students_qs.distinct().order_by("long_name", "student_id")

    page_obj = Paginator(students_qs, 100).get_page(request.GET.get("page"))
    student_ids = [student.id for student in page_obj]
    grades_qs = Grade.objects.none()
    if student_ids:
        grades_qs = (
            Grade.objects.select_related(
                "student",
                "student__user",
                "section__semester__academic_year",
                "section__curriculum_course__course",
                "section__curriculum_course__credit_hours",
                "section__faculty__staff_profile__user",
                "value",
            )
            .filter(student_id__in=student_ids)
            .order_by(
                "student__long_name",
                "-section__semester__start_date",
                "-section__semester__number",
                "section__curriculum_course__course__short_code",
            )
        )
    if semester_id:
        grades_qs = grades_qs.filter(section__semester_id=semester_id)

    registrations_qs = Registration.objects.none()
    if selected_student_id and student_ids:
        registrations_qs = (
            Registration.objects.select_related(
                "student",
                "student__user",
                "section__semester__academic_year",
                "section__curriculum_course__course",
                "section__curriculum_course__credit_hours",
                "section__faculty__staff_profile__user",
            )
            .filter(student_id__in=student_ids)
            .order_by(
                "student__long_name",
                "-section__semester__start_date",
                "-section__semester__number",
                "section__curriculum_course__course__short_code",
            )
        )
        if semester_id:
            registrations_qs = registrations_qs.filter(section__semester_id=semester_id)

    student_groups = build_student_grade_groups(
        list(page_obj),
        grades_qs,
        registrations_qs,
        can_manage_grades=can_manage_grades,
    )
    all_semesters_selected = semester_id is None
    pagination_query, pagination_hidden_fields = _pagination_hidden_fields(request)
    selected_student_label = ""
    selected_student_snapshot: RegStudentSnapshotT | None = None
    if selected_student_id:
        selected_student = (
            Student.objects.select_related("user").filter(id=selected_student_id).first()
        )
        if selected_student:
            selected_student_label = _student_label(selected_student)
            selected_student_snapshot = build_reg_student_snapshot(
                selected_student,
                semester_param if semester_param_present else "all",
            )

    return {
        "page_title": "Registrar grades",
        "page_summary": "Find students, review grades, and download transcripts.",
        "eyebrow": "Registrar",
        "sidebar_links": build_staff_sidebar_links(sidebar_role, "grades"),
        "role_switcher": build_staff_role_switcher(user, "registrar"),
        "breadcrumbs": [
            {
                "label": "Registrar dashboard",
                "href": reverse("staff_role_dashboard", args=["registrar"]),
            },
            {"label": "Grade review", "href": ""},
        ],
        "student_groups": student_groups,
        "page_obj": page_obj,
        "semester_options": _semester_options(semester_id, all_semesters_selected),
        "selected_student_id": selected_student_id,
        "selected_student_label": selected_student_label,
        "selected_student_snapshot": selected_student_snapshot,
        "bulk_download_url": reverse("reg_grade_transcripts_bulk_pdf"),
        "registrar_admin_links": _admin_shortcuts_for_models(
            user,
            REGISTRAR_ADMIN_SHORTCUTS,
        ),
        "pagination_query": pagination_query,
        "pagination_hidden_fields": pagination_hidden_fields,
        "pagination_action": request.path,
        "student_autocomplete_url": reverse("reg_std_autocomplete"),
    }


def _grade_editor_url(
    student_id: int,
    semester_id: int,
    can_manage_grades: bool,
) -> str:
    """Return the registrar grade editor URL when this actor may use it."""
    if not can_manage_grades:
        return ""
    return reverse("reg_grade_semester_editor", args=[student_id, semester_id])


def _semester_group(
    student_id: int,
    semester: Semester,
    can_manage_grades: bool,
) -> RegSemGpT:
    """Return an initialized semester grade group."""
    return RegSemGpT(
        semester=semester,
        label=f"{semester.academic_year.code} · Semester {semester.number}",
        rows=[],
        credits_total=0,
        gpa="N/A",
        grade_editor_url=_grade_editor_url(student_id, semester.id, can_manage_grades),
        can_manage_grades=can_manage_grades,
    )


def _faculty_label_for_section(section: Section) -> str:
    """Return the faculty label used in registrar grade tables."""
    faculty_label = "TBA"
    if section.faculty and section.faculty.staff_profile:
        faculty_label = section.faculty.staff_profile.user.get_full_name() or str(
            section.faculty.staff_profile
        )
    return faculty_label


def _section_credits(section: Section) -> int:
    """Return integer credit hours for a section."""
    return int(section.curriculum_course.credit_hours.code)


def build_student_grade_groups(
    students: list[Student],
    grades: Iterable[Grade],
    registrations: Iterable[Registration] | None = None,
    *,
    can_manage_grades: bool = False,
) -> list[RegStdGpT]:
    """Group grade rows by student and semester for registrar pages."""
    student_groups: list[RegStdGpT] = []
    student_lookup: dict[int, RegStdGpT] = {}
    semester_lookup_map: dict[int, dict[int, RegSemGpT]] = {}
    graded_sections_by_student_semester: dict[tuple[int, int], set[int]] = {}
    student_gpa_points: dict[int, float] = {}
    student_gpa_credits: dict[int, int] = {}
    semester_gpa_points: dict[tuple[int, int], float] = {}
    semester_gpa_credits: dict[tuple[int, int], int] = {}
    for student in students:
        student_group = RegStdGpT(
            student=student,
            std_label=student.long_name or student.user.get_full_name(),
            student_id=student.student_id or "Pending ID",
            semesters=[],
            credits_total=0,
            gpa="N/A",
        )
        student_groups.append(student_group)
        student_lookup[student.id] = student_group
        semester_lookup_map[student.id] = {}
        student_gpa_points[student.id] = 0.0
        student_gpa_credits[student.id] = 0

    for grade in grades:
        grade_student_group = student_lookup.get(grade.student_id)
        if grade_student_group is None:
            continue
        semester_group_lookup = semester_lookup_map[grade.student_id]
        semester = grade.section.semester
        current_semester_group = semester_group_lookup.get(semester.id)
        if current_semester_group is None:
            current_semester_group = _semester_group(
                grade.student_id,
                semester,
                can_manage_grades,
            )
            semester_group_lookup[semester.id] = current_semester_group
            grade_student_group["semesters"].append(current_semester_group)
            semester_gpa_points[(grade.student_id, semester.id)] = 0.0
            semester_gpa_credits[(grade.student_id, semester.id)] = 0
        semester_key = (grade.student_id, semester.id)
        graded_sections_by_student_semester.setdefault(semester_key, set()).add(
            grade.section_id
        )
        faculty_label = _faculty_label_for_section(grade.section)
        course = grade.section.curriculum_course.course
        credits = _section_credits(grade.section)
        grade_label = (
            grade.value.code.upper() if grade.value and grade.value.code else "-"
        )
        current_semester_group["rows"].append(
            {
                "course_code": course.short_code or course.code or "",
                "course_title": course.title or "",
                "credits": credits,
                "grade": grade_label,
                "faculty": faculty_label,
                "roster_url": reverse(
                    "reg_class_roster_detail",
                    args=[grade.section_id],
                ),
                "is_missing_grade": False,
            }
        )
        current_semester_group["credits_total"] += credits
        grade_student_group["credits_total"] += credits
        gpa_values = get_grade_points_and_credits(grade)
        if gpa_values is None:
            continue
        quality_points, gpa_credits = gpa_values
        semester_gpa_points[semester_key] += quality_points
        semester_gpa_credits[semester_key] += gpa_credits
        student_gpa_points[grade.student_id] += quality_points
        student_gpa_credits[grade.student_id] += gpa_credits

    for registration in registrations or []:
        grade_student_group = student_lookup.get(registration.student_id)
        if grade_student_group is None:
            continue
        semester = registration.section.semester
        semester_key = (registration.student_id, semester.id)
        if registration.section_id in graded_sections_by_student_semester.get(
            semester_key,
            set(),
        ):
            continue
        semester_group_lookup = semester_lookup_map[registration.student_id]
        current_semester_group = semester_group_lookup.get(semester.id)
        if current_semester_group is None:
            current_semester_group = _semester_group(
                registration.student_id,
                semester,
                can_manage_grades,
            )
            semester_group_lookup[semester.id] = current_semester_group
            grade_student_group["semesters"].append(current_semester_group)
            semester_gpa_points[semester_key] = 0.0
            semester_gpa_credits[semester_key] = 0
        section = registration.section
        course = section.curriculum_course.course
        credits = _section_credits(section)
        current_semester_group["rows"].append(
            {
                "course_code": course.short_code or course.code or "",
                "course_title": course.title or "",
                "credits": credits,
                "grade": "-",
                "faculty": _faculty_label_for_section(section),
                "roster_url": reverse("reg_class_roster_detail", args=[section.id]),
                "is_missing_grade": True,
            }
        )
        current_semester_group["credits_total"] += credits
        grade_student_group["credits_total"] += credits

    for student_group in student_groups:
        student_id = student_group["student"].id
        total_credits = student_gpa_credits.get(student_id, 0)
        if total_credits:
            student_group["gpa"] = f"{student_gpa_points[student_id] / total_credits:.2f}"
        for semester_group in student_group["semesters"]:
            semester_key = (student_id, semester_group["semester"].id)
            sem_credits = semester_gpa_credits.get(semester_key, 0)
            if sem_credits:
                semester_group["gpa"] = (
                    f"{semester_gpa_points[semester_key] / sem_credits:.2f}"
                )
    return student_groups


def build_reg_grade_transcript_context(request: HttpRequest, student_id: int) -> ContextT:
    """Build context for an official grade transcript preview."""
    user = cast(User, request.user)
    sidebar_role = registrar_sidebar_role(user)
    transcript = build_transcript_document(student_id)
    return {
        "page_title": "Official grade transcript",
        "page_summary": "Registrar-issued transcript preview.",
        "eyebrow": "Registrar",
        "std_label": transcript["student_name"],
        "curriculum_label": transcript["major_program"],
        "generated_at": transcript["printed_date"],
        "transcript": transcript,
        "transcript_rows": flatten_transcript_rows(transcript),
        "sidebar_links": build_staff_sidebar_links(sidebar_role, "grades"),
        "role_switcher": build_staff_role_switcher(user, "registrar"),
        "dashboard_url": reverse("reg_grades_dashboard"),
        "download_url": reverse("reg_grade_transcript_pdf", args=[student_id]),
        "source_url": reverse("reg_grade_transcript_org", args=[student_id]),
    }


def update_semester_window(semester_id: str | None, status_code: str | None) -> str:
    """Update one semester window and return the user-facing success text."""
    SemesterStatus._populate_attributes_and_db()
    statuses = set(SemesterStatus.objects.values_list("code", flat=True))
    if status_code not in statuses:
        raise ValueError("Unknown status.")
    semester = get_object_or_404(Semester, pk=semester_id)
    semester.status_id = status_code
    semester.save(update_fields=["status"])
    return f"{semester} status updated to {semester.status.label}."


def build_reg_windows_context(request: HttpRequest) -> ContextT:
    """Build context for registration and grade-entry window management."""
    SemesterStatus._populate_attributes_and_db()
    semesters = (
        Semester.objects.select_related("academic_year", "status")
        .order_by("-academic_year__start_date", "-number")
        .all()
    )
    return {
        "semester_groups": group_semester_windows(list(semesters)),
        "statuses": SemesterStatus.objects.all().order_by("code"),
        "page_title": "Semester windows",
        "page_summary": "Open registration and grade-entry periods from Tusis.",
        "eyebrow": "Registrar officer",
        "sidebar_links": build_staff_sidebar_links("reg_officer", "semester_windows"),
        "role_switcher": build_staff_role_switcher(cast(User, request.user), "registrar"),
        "breadcrumbs": [
            {
                "label": "Registrar dashboard",
                "href": reverse("staff_role_dashboard", args=["registrar"]),
            },
            {"label": "Semester windows", "href": ""},
        ],
    }
