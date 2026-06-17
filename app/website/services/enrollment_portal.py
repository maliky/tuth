"""Enrollment portal helpers for student directory and profile workflows."""

from __future__ import annotations

from typing import TypeAlias, TypedDict

from django.contrib.auth.models import User
from django.core.paginator import Page, Paginator
from django.db import models
from django.db.models import Q, QuerySet
from django.http import HttpRequest, QueryDict
from django.urls import reverse

from app.academics.models.college import College
from app.academics.models.curriculum import Curriculum
from app.people.models.student import Student
from app.registry.models.document import DocStd
from app.registry.models.grade import Grade
from app.registry.models.registration import Registration
from app.timetable.models.semester import Semester
from app.website.services.portal_types import AdminShortcutT
from app.website.services.staff_common import _admin_shortcuts_for_models

StudentFilterValueT: TypeAlias = str | int | None
StudentSummaryRowT: TypeAlias = dict[str, str]
StudentResultT: TypeAlias = dict[str, str | int]
AdminShortcutSpecT: TypeAlias = tuple[str, type[models.Model]]

ENROLLMENT_OFFICER_GROUP = "Enrollment Officer"
STUDENT_DIRECTORY_PAGE_SIZE = 25
ENROLLMENT_ADMIN_SHORTCUTS: tuple[AdminShortcutSpecT, ...] = (
    ("Students", Student),
    ("Student documents", DocStd),
    ("Registrations", Registration),
    ("Programs / curricula", Curriculum),
    ("Colleges", College),
    ("Semesters", Semester),
    ("User accounts", User),
)


class StudentFiltersT(TypedDict):
    """Normalized filters used by enrollment student search pages."""

    q: str
    college: StudentFilterValueT
    program: StudentFilterValueT
    semester: StudentFilterValueT


def clean_int(value: object) -> int | None:
    """Return an integer id from request data, or None when empty/invalid."""
    try:
        text = str(value or "").strip()
        return int(text) if text else None
    except (TypeError, ValueError):
        return None


def enrollment_admin_shortcuts(user: User) -> list[AdminShortcutT]:
    """Return officer-only admin shortcuts for tables the user may view."""
    if not user.is_staff:
        return []
    if not user.groups.filter(name=ENROLLMENT_OFFICER_GROUP).exists():
        return []
    return _admin_shortcuts_for_models(user, ENROLLMENT_ADMIN_SHORTCUTS)


def student_search_queryset() -> QuerySet[Student]:
    """Return the base student queryset used by enrollment search screens."""
    return Student.objects.select_related(
        "user",
        "entry_semester__academic_year",
        "last_enrolled_semester__academic_year",
    ).prefetch_related("curriculum_enrollments__curriculum__college")


def parse_student_filters(params: QueryDict) -> StudentFiltersT:
    """Normalize student directory filters from request query parameters."""
    return {
        "q": str(params.get("q") or "").strip(),
        "college": clean_int(params.get("college")),
        "program": clean_int(params.get("program")),
        "semester": clean_int(params.get("semester")),
    }


def apply_student_filters(
    queryset: QuerySet[Student],
    filters: StudentFiltersT,
) -> QuerySet[Student]:
    """Apply directory and autocomplete filters to a student queryset."""
    q_value = filters["q"]
    if q_value:
        text_query = (
            Q(student_id__icontains=q_value)
            | Q(long_name__icontains=q_value)
            | Q(user__username__icontains=q_value)
            | Q(user__first_name__icontains=q_value)
            | Q(user__last_name__icontains=q_value)
            | Q(curricula__short_name__icontains=q_value)
            | Q(curricula__long_name__icontains=q_value)
            | Q(curricula__college__code__icontains=q_value)
            | Q(curricula__college__long_name__icontains=q_value)
            | Q(entry_semester__academic_year__code__icontains=q_value)
            | Q(entry_semester__academic_year__long_name__icontains=q_value)
            | Q(last_enrolled_semester__academic_year__code__icontains=q_value)
            | Q(last_enrolled_semester__academic_year__long_name__icontains=q_value)
        )
        semester_number = clean_int(q_value)
        if semester_number is not None:
            text_query |= Q(entry_semester__number=semester_number) | Q(
                last_enrolled_semester__number=semester_number
            )
        queryset = queryset.filter(text_query)

    college_id = filters["college"]
    if college_id:
        queryset = queryset.filter(curricula__college_id=college_id)

    program_id = filters["program"]
    if program_id:
        queryset = queryset.filter(curricula__id=program_id)

    semester_id = filters["semester"]
    if semester_id:
        queryset = queryset.filter(
            Q(entry_semester_id=semester_id)
            | Q(last_enrolled_semester_id=semester_id)
            | Q(student_registrations__section__semester_id=semester_id)
        )

    return queryset.distinct()


def _query_without_page(params: QueryDict) -> str:
    """Return the current query string without pagination state."""
    query = params.copy()
    query.pop("page", None)
    for key in list(query.keys()):
        if not query.get(key):
            query.pop(key, None)
    return query.urlencode()


def _program_label(curriculum: Curriculum) -> str:
    """Return a readable program label for lists and autocomplete."""
    long_name = curriculum.long_name or curriculum.short_name
    return f"{curriculum.college.code} · {curriculum.short_name} · {long_name}"


def build_student_directory_context(request: HttpRequest) -> dict[str, object]:
    """Build context for the enrollment student directory."""
    filters = parse_student_filters(request.GET)
    queryset = apply_student_filters(student_search_queryset(), filters).order_by(
        "long_name", "student_id"
    )
    paginator = Paginator(queryset, STUDENT_DIRECTORY_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))
    return {
        "students": page_obj.object_list,
        "page_obj": page_obj,
        "pagination_query": _query_without_page(request.GET),
        "filters": filters,
        "colleges": College.objects.order_by("code", "long_name"),
        "programs": Curriculum.objects.select_related("college").order_by(
            "college__code", "long_name", "short_name"
        ),
        "semesters": Semester.objects.select_related("academic_year").order_by(
            "-academic_year__start_date", "-number"
        ),
    }


def student_result_label(student: Student) -> str:
    """Return a rich autocomplete label for one student."""
    program = student.primary_curriculum
    semester = student.last_enrolled_semester or student.entry_semester
    semester_label = str(semester) if semester else "No semester"
    return (
        f"{student.student_id} - {student.long_name} | "
        f"{program.college.code} {program.short_name} | {semester_label}"
    )


def build_student_autocomplete_results(request: HttpRequest) -> list[StudentResultT]:
    """Return JSON-ready student suggestions for lookup widgets."""
    filters = parse_student_filters(request.GET)
    if not any(filters.values()):
        return []
    suggestions = apply_student_filters(student_search_queryset(), filters).order_by(
        "student_id", "long_name"
    )[:15]
    return [
        {
            "pk": student.pk,
            "label": student_result_label(student),
            "student_id": student.student_id,
            "curriculum": student.primary_curriculum.short_name,
            "college": student.primary_curriculum.college.code,
            "semester": str(
                student.last_enrolled_semester or student.entry_semester or ""
            ),
        }
        for student in suggestions
    ]


def build_curriculum_autocomplete_results(request: HttpRequest) -> list[StudentResultT]:
    """Return JSON-ready curriculum suggestions for program selection."""
    query = str(request.GET.get("q") or "").strip()
    curricula = Curriculum.objects.select_related("college").order_by(
        "college__code", "long_name", "short_name"
    )
    if query:
        curricula = curricula.filter(
            Q(short_name__icontains=query)
            | Q(long_name__icontains=query)
            | Q(college__code__icontains=query)
            | Q(college__long_name__icontains=query)
        )
    return [
        {
            "id": curriculum.id,
            "pk": curriculum.id,
            "label": _program_label(curriculum),
            "text": _program_label(curriculum),
        }
        for curriculum in curricula[:20]
    ]


def _value(value: object) -> str:
    """Return a display value with a consistent empty-state label."""
    text = str(value or "").strip()
    return text or "Not set"


def _summary_rows(pairs: tuple[tuple[str, object], ...]) -> list[StudentSummaryRowT]:
    """Build label/value rows for student detail cards."""
    return [{"label": label, "value": _value(value)} for label, value in pairs]


def _page_for_student_detail(student: Student) -> Page[Registration]:
    """Return the first page of recent student registrations for profile context."""
    registrations = (
        Registration.objects.filter(student=student)
        .select_related(
            "status",
            "section__semester__academic_year",
            "section__curriculum_course__course",
        )
        .order_by(
            "-section__semester__academic_year__start_date",
            "-section__semester__number",
            "section__curriculum_course__course__short_code",
        )
    )
    return Paginator(registrations, 8).get_page(1)


def build_student_detail_context(student: Student, user: User) -> dict[str, object]:
    """Build grouped profile context for enrollment student review."""
    curriculum_rows = list(
        student.curriculum_enrollments.select_related(
            "curriculum__college", "entry_semester", "exit_semester"
        ).order_by("-is_primary", "-is_active", "-updated_at")
    )
    docs = list(
        DocStd.objects.filter(person=student)
        .select_related("document_type", "status")
        .order_by("-id")[:6]
    )
    grades = Grade.objects.filter(student=student).select_related("value")
    return {
        "identity_rows": _summary_rows(
            (
                ("Student ID", student.student_id),
                ("Username", student.username),
                ("Full name", student.long_name),
                ("Email", student.email),
                ("Phone", student.phone_number),
                ("Birth date", student.birth_date),
                ("Birth place", student.birth_place),
            )
        ),
        "enrollment_rows": _summary_rows(
            (
                ("Program / Curriculum", student.primary_curriculum),
                ("College", student.primary_curriculum.college),
                ("Entry semester", student.entry_semester),
                ("Current semester", student.last_enrolled_semester),
                ("Max credits", student.max_credit_hours),
                ("Class level", student.class_level),
            )
        ),
        "bio_rows": _summary_rows(
            (
                ("Gender", student.get_gender_display()),
                ("Nationality", student.nationality),
                ("Origin county", student.origin_county),
                ("Marital status", student.marital_status),
                ("Physical address", student.physical_address),
            )
        ),
        "family_rows": _summary_rows(
            (
                ("Last school attended", student.last_school_attended),
                ("Reason for leaving", student.reason_for_leaving),
                ("Father", student.father_name),
                ("Father address", student.father_address),
                ("Mother", student.mother_name),
                ("Mother address", student.mother_address),
                ("Emergency contact", student.emergency_contact),
            )
        ),
        "curriculum_rows": curriculum_rows,
        "documents": docs,
        "registration_page": _page_for_student_detail(student),
        "grade_count": grades.count(),
        "passing_grade_count": grades.filter(value__number__gte=1).count(),
        "admin_shortcuts": enrollment_admin_shortcuts(user),
        "admin_student_url": reverse("admin:people_student_change", args=[student.pk])
        if user.is_staff and user.has_perm("people.change_student")
        else "",
    }


__all__ = [
    "apply_student_filters",
    "build_curriculum_autocomplete_results",
    "build_student_autocomplete_results",
    "build_student_detail_context",
    "build_student_directory_context",
    "clean_int",
    "enrollment_admin_shortcuts",
    "parse_student_filters",
    "student_result_label",
    "student_search_queryset",
    "StudentFiltersT",
]
