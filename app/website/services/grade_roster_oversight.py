"""Read-only grade roster oversight services for academic leadership."""

from __future__ import annotations

from typing import TypeAlias, TypedDict, cast

from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Q, QuerySet
from django.http import Http404, HttpRequest, QueryDict
from django.shortcuts import get_object_or_404
from django.urls import reverse

from app.people.models.faculty import Faculty
from app.people.models.role_assignment import RoleAssignment
from app.people.models.student import Student
from app.registry.models.grade import Grade
from app.registry.models.registration import Registration
from app.shared.auth.perms import UserRole
from app.shared.utils import parse_str
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester
from app.website.services.portal_types import BreadcrumbT, PortalContextT
from app.website.services.staff_common import (
    _admin_shortcuts_for_models,
    _as_user,
    get_faculty_profile,
)
from app.website.services.staff_roles import (
    ROLE_CONFIG,
    build_staff_role_switcher,
    build_staff_sidebar_links,
)
from app.website.services.transcript_document import (
    build_transcript_document,
    flatten_transcript_rows,
)

OVERSIGHT_ROLE_SLUGS = frozenset({"chair", "dean", "vpaa"})
ROSTER_PAGE_SIZE = 25

SectionQueryT: TypeAlias = QuerySet[Section]
GradeQueryT: TypeAlias = QuerySet[Grade]
RoleAssignmentQueryT: TypeAlias = QuerySet[RoleAssignment]


class FilterOptionT(TypedDict):
    """One HTML select option for roster filters."""

    value: str
    label: str
    selected: bool


class AutocompleteResultT(TypedDict):
    """Select2-compatible autocomplete item."""

    id: int
    text: str


class GradeRosterSummaryRowT(TypedDict):
    """One section row in an oversight roster summary."""

    section: Section
    course_code: str
    course_title: str
    faculty_label: str
    roster_count: int
    graded_count: int
    pending_count: int
    grade_entry_open: bool
    detail_url: str


class GradeRosterDetailRowT(TypedDict):
    """One student row in a read-only section roster."""

    student_label: str
    student_id: str
    registration_status: str
    grade_code: str
    grade_status: str


class GradeTranscriptSummaryRowT(TypedDict):
    """One student row in an academic transcript oversight index."""

    student: Student
    student_label: str
    student_id: str
    grade_count: int
    section_count: int
    latest_semester_label: str
    detail_url: str


OVERSIGHT_ADMIN_SHORTCUTS = (
    ("Students", Student),
    ("Registrations", Registration),
    ("Grades", Grade),
    ("Sections", Section),
)


def clean_int(value: str | None) -> int | None:
    """Return an integer for a clean query parameter, otherwise None."""
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _base_section_queryset() -> SectionQueryT:
    """Return the hydrated base queryset for oversight roster pages."""
    return Section.objects.select_related(
        "faculty__staff_profile__user",
        "faculty__staff_profile__department",
        "faculty__college",
        "semester__academic_year",
        "semester__status",
        "curriculum_course__course__department__college",
        "curriculum_course__course",
    ).exclude(faculty__isnull=True)


def _active_role_assignments(user: User, role_slug: str) -> RoleAssignmentQueryT:
    """Return active academic role assignments that can scope oversight data."""
    role_groups = {
        "chair": UserRole.CHAIR.value.label,
        "dean": UserRole.DEAN.value.label,
    }
    group_name = role_groups.get(role_slug)
    if not group_name:
        return RoleAssignment.objects.none()
    return RoleAssignment.objects.filter(
        user=user,
        group__name=group_name,
        end_date__isnull=True,
    ).select_related("college", "department")


def _assignment_section_filter(user: User, role_slug: str) -> Q | None:
    """Return the section filter from scoped role assignments, if available."""
    assignments = list(_active_role_assignments(user, role_slug))
    department_ids = [row.department_id for row in assignments if row.department_id]
    college_ids = [row.college_id for row in assignments if row.college_id]
    scope_filter = Q()
    has_scope = False
    if department_ids:
        scope_filter |= Q(
            curriculum_course__course__department_id__in=department_ids,
        )
        has_scope = True
    if college_ids:
        scope_filter |= Q(
            curriculum_course__course__department__college_id__in=college_ids,
        )
        has_scope = True
    return scope_filter if has_scope else None


def _assignment_scope_label(user: User, role_slug: str) -> str | None:
    """Return a readable label for role-assignment based oversight scope."""
    labels: list[str] = []
    seen: set[str] = set()
    for assignment in _active_role_assignments(user, role_slug):
        target = assignment.department or assignment.college
        if target is None:
            continue
        label = str(target)
        if label in seen:
            continue
        labels.append(label)
        seen.add(label)
    return ", ".join(labels) if labels else None


def _course_code(section: Section) -> str:
    """Return a familiar course code for list and detail pages."""
    course = section.curriculum_course.course
    return course.short_code or course.code or str(course)


def scoped_grade_roster_sections(user: User, role_slug: str) -> SectionQueryT:
    """Return sections visible to a Chair, Dean, or VPAA oversight role."""
    sections = _base_section_queryset()
    if role_slug == "vpaa":
        return sections

    # Prefer explicit role assignments so staff-only deans/chairs still get
    # the scoped roster and autocomplete data attached to their assignment.
    assignment_filter = _assignment_section_filter(user, role_slug)
    if assignment_filter is not None:
        return sections.filter(assignment_filter).distinct()

    faculty = get_faculty_profile(user)
    if faculty is None:
        return sections.none()

    if role_slug == "dean":
        if not faculty.college_id:
            return sections.none()
        return sections.filter(
            curriculum_course__course__department__college_id=faculty.college_id
        )

    if role_slug == "chair":
        department = faculty.staff_profile.department
        if department:
            return sections.filter(curriculum_course__course__department=department)
        if faculty.college_id:
            return sections.filter(
                curriculum_course__course__department__college_id=faculty.college_id
            )
    return sections.none()


def _filtered_sections(user: User, role_slug: str, params: QueryDict) -> SectionQueryT:
    """Apply student, faculty, and semester filters inside the role scope."""
    selected_student_id = clean_int(params.get("student_id"))
    selected_faculty_id = clean_int(params.get("faculty_id"))
    semester_param = params.get("semester")
    semester_id = None if semester_param == "all" else clean_int(semester_param)
    sections = scoped_grade_roster_sections(user, role_slug)
    if selected_student_id:
        sections = sections.filter(section_registrations__student_id=selected_student_id)
    if selected_faculty_id:
        sections = sections.filter(faculty_id=selected_faculty_id)
    if semester_id:
        sections = sections.filter(semester_id=semester_id)
    return sections.distinct()


def _filtered_transcript_grades(
    user: User,
    role_slug: str,
    params: QueryDict,
) -> GradeQueryT:
    """Return grade rows whose course sections are visible to the role."""
    selected_student_id = clean_int(params.get("student_id"))
    semester_param = params.get("semester")
    semester_id = None if semester_param == "all" else clean_int(semester_param)
    scoped_section_ids = scoped_grade_roster_sections(user, role_slug).values_list(
        "id",
        flat=True,
    )
    grades = Grade.objects.filter(section_id__in=scoped_section_ids)
    if selected_student_id:
        grades = grades.filter(student_id=selected_student_id)
    if semester_id:
        grades = grades.filter(section__semester_id=semester_id)
    return grades


def _semester_options(semester_id: int | None) -> list[FilterOptionT]:
    """Return semester filter options for the oversight roster page."""
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


def _student_label(student: Student) -> str:
    """Return a concise student label for filters and roster rows."""
    return student.long_name or student.user.get_full_name() or student.username


def _student_filter_label(student_id: int | None) -> str:
    """Return the label for the currently selected student filter."""
    if student_id is None:
        return ""
    student = Student.objects.select_related("user").filter(pk=student_id).first()
    if student is None:
        return ""
    return f"{student.student_id} - {_student_label(student)}"


def _faculty_filter_label(faculty: Faculty | None) -> str:
    """Return a faculty label with a stable identifier for filter controls."""
    if faculty is None:
        return ""
    staff = faculty.staff_profile
    user = staff.user
    name = staff.long_name or user.get_full_name() or user.username
    identifier = staff.staff_id or user.username
    return f"{name} ({identifier})"


def _selected_faculty_filter_label(faculty_id: int | None) -> str:
    """Return the label for the currently selected faculty filter."""
    if faculty_id is None:
        return ""
    faculty = (
        Faculty.objects.select_related("staff_profile__user")
        .filter(pk=faculty_id)
        .first()
    )
    return _faculty_filter_label(faculty)


def _section_counts(section_ids: list[int]) -> tuple[dict[int, int], dict[int, int]]:
    """Return roster and graded counts keyed by section id."""
    roster_counts: dict[int, int] = {}
    graded_counts: dict[int, int] = {}
    for section_id in section_ids:
        roster_counts[section_id] = Registration.objects.filter(
            section_id=section_id
        ).count()
        graded_counts[section_id] = Grade.objects.filter(
            section_id=section_id,
            value__isnull=False,
        ).count()
    return roster_counts, graded_counts


def _faculty_label(section: Section) -> str:
    """Return the display label for the assigned section faculty."""
    faculty = section.faculty
    if faculty is None:
        return "Unassigned"
    staff_profile = faculty.staff_profile
    user = staff_profile.user
    return staff_profile.long_name or user.get_full_name() or user.username


def _scope_label(user: User, role_slug: str) -> str:
    """Return a concise human-readable label for the current oversight scope."""
    if role_slug == "vpaa":
        return "Institution"
    assignment_label = _assignment_scope_label(user, role_slug)
    if assignment_label:
        return assignment_label
    faculty = get_faculty_profile(user)
    if faculty is None:
        return "No academic assignment"
    if role_slug == "dean" and faculty.college:
        return str(faculty.college)
    if role_slug == "chair":
        department = faculty.staff_profile.department
        if department:
            return str(department)
        if faculty.college:
            return str(faculty.college)
    return "No academic assignment"


def _role_title(role_slug: str) -> str:
    """Return the configured role title for an oversight page."""
    config = ROLE_CONFIG.get(role_slug, {})
    title = str(config.get("title") or role_slug.replace("_", " ").title())
    return title


def build_grade_roster_list_context(
    request: HttpRequest,
    role_slug: str,
) -> PortalContextT:
    """Build the read-only roster summary page for academic oversight."""
    user = _as_user(request.user)
    semester_param = request.GET.get("semester")
    semester_id = None if semester_param == "all" else clean_int(semester_param)
    selected_student_id = clean_int(request.GET.get("student_id"))
    selected_faculty_id = clean_int(request.GET.get("faculty_id"))
    ordered_sections = _filtered_sections(user, role_slug, request.GET).order_by(
        "-semester__academic_year__start_date",
        "-semester__number",
        "curriculum_course__course__department__code",
        "curriculum_course__course__number",
        "number",
    )
    paginator = Paginator(ordered_sections, ROSTER_PAGE_SIZE)
    section_page = paginator.get_page(request.GET.get("page"))
    sections = list(cast(list[Section], section_page.object_list))
    section_ids = [section.id for section in sections]
    roster_counts, graded_counts = _section_counts(section_ids)
    rows: list[GradeRosterSummaryRowT] = []
    for section in sections:
        roster_count = roster_counts.get(section.id, 0)
        graded_count = graded_counts.get(section.id, 0)
        rows.append(
            {
                "section": section,
                "course_code": _course_code(section),
                "course_title": section.curriculum_course.course.title or "",
                "faculty_label": _faculty_label(section),
                "roster_count": roster_count,
                "graded_count": graded_count,
                "pending_count": max(roster_count - graded_count, 0),
                "grade_entry_open": section.semester.status_id == "grade_entry",
                "detail_url": reverse(
                    "staff_grade_roster_detail",
                    args=[role_slug, section.id],
                ),
            }
        )

    role_title = _role_title(role_slug)
    pagination_query, pagination_hidden_fields = _pagination_hidden_fields(request.GET)
    return {
        "page_title": f"{role_title} grade rosters",
        "page_summary": "Read-only class roster and submitted grade oversight.",
        "eyebrow": role_slug.replace("_", " ").title(),
        "sidebar_links": build_staff_sidebar_links(role_slug, "grade_rosters"),
        "role_switcher": build_staff_role_switcher(user, role_slug),
        "breadcrumbs": _oversight_breadcrumbs(role_slug, ""),
        "dashboard_url": reverse("staff_role_dashboard", args=[role_slug]),
        "role_slug": role_slug,
        "scope_label": _scope_label(user, role_slug),
        "student_autocomplete_url": reverse(
            "staff_grade_roster_student_autocomplete",
            args=[role_slug],
        ),
        "faculty_autocomplete_url": reverse(
            "staff_grade_roster_faculty_autocomplete",
            args=[role_slug],
        ),
        "semester_options": _semester_options(semester_id),
        "selected_student_id": selected_student_id,
        "selected_student_label": _student_filter_label(selected_student_id),
        "selected_faculty_id": selected_faculty_id,
        "selected_faculty_label": _selected_faculty_filter_label(selected_faculty_id),
        "section_page": section_page,
        "section_rows": rows,
        "oversight_admin_links": _admin_shortcuts_for_models(
            user,
            OVERSIGHT_ADMIN_SHORTCUTS,
        ),
        "pagination_query": pagination_query,
        "pagination_hidden_fields": pagination_hidden_fields,
        "pagination_action": request.path,
    }


def build_grade_roster_detail_context(
    request: HttpRequest,
    role_slug: str,
    section_id: int,
) -> PortalContextT:
    """Build one read-only class roster with grade values for oversight roles."""
    user = _as_user(request.user)
    section = get_object_or_404(
        scoped_grade_roster_sections(user, role_slug),
        pk=section_id,
    )
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
    rows: list[GradeRosterDetailRowT] = []
    for registration in registrations:
        student = registration.student
        grade = grade_map.get(student.id)
        rows.append(
            {
                "student_label": _student_label(student),
                "student_id": student.student_id or str(student.id),
                "registration_status": str(registration.status),
                "grade_code": grade.value.code.upper() if grade and grade.value else "",
                "grade_status": "Submitted" if grade and grade.value else "Pending",
            }
        )

    course_code = _course_code(section)
    role_title = _role_title(role_slug)
    return {
        "page_title": f"{course_code} roster",
        "page_summary": "Read-only roster; faculty owns grade entry.",
        "eyebrow": role_slug.replace("_", " ").title(),
        "sidebar_links": build_staff_sidebar_links(role_slug, "grade_rosters"),
        "role_switcher": build_staff_role_switcher(user, role_slug),
        "breadcrumbs": _oversight_breadcrumbs(role_slug, course_code),
        "dashboard_url": reverse("staff_role_dashboard", args=[role_slug]),
        "list_url": reverse("staff_grade_rosters", args=[role_slug]),
        "role_title": role_title,
        "role_slug": role_slug,
        "section": section,
        "course_code": course_code,
        "course_title": section.curriculum_course.course.title or "",
        "faculty_label": _faculty_label(section),
        "grade_rows": rows,
    }


def _transcript_latest_semester_labels(grades: GradeQueryT) -> dict[int, str]:
    """Return the latest scoped semester label for each student in a grade set."""
    labels: dict[int, str] = {}
    ordered_grades = grades.select_related("section__semester__academic_year").order_by(
        "student_id",
        "-section__semester__start_date",
        "-section__semester_id",
        "-section_id",
    )
    for grade in ordered_grades:
        if grade.student_id in labels:
            continue
        semester = grade.section.semester
        labels[grade.student_id] = (
            f"{semester.academic_year.code} · Semester {semester.number}"
        )
    return labels


def build_grade_transcript_list_context(
    request: HttpRequest,
    role_slug: str,
) -> PortalContextT:
    """Build the student transcript index for academic oversight roles."""
    user = _as_user(request.user)
    semester_param = request.GET.get("semester")
    semester_id = None if semester_param == "all" else clean_int(semester_param)
    selected_student_id = clean_int(request.GET.get("student_id"))
    scoped_grades = _filtered_transcript_grades(user, role_slug, request.GET)
    student_ids = scoped_grades.values_list("student_id", flat=True).distinct()
    ordered_students = (
        Student.objects.select_related("user")
        .filter(id__in=student_ids)
        .order_by("long_name", "student_id", "id")
    )
    paginator = Paginator(ordered_students, ROSTER_PAGE_SIZE)
    student_page = paginator.get_page(request.GET.get("page"))
    students = list(cast(list[Student], student_page.object_list))
    page_student_ids = [student.id for student in students]
    page_grades = scoped_grades.filter(student_id__in=page_student_ids)
    grade_stats: dict[int, dict[str, int]] = {}
    student_section_ids: dict[int, set[int]] = {}
    for grade in page_grades.only("student_id", "section_id"):
        stats = grade_stats.setdefault(
            grade.student_id,
            {"grade_count": 0, "section_count": 0},
        )
        stats["grade_count"] += 1
        student_section_ids.setdefault(grade.student_id, set()).add(grade.section_id)
    for student_id, section_ids in student_section_ids.items():
        grade_stats[student_id]["section_count"] = len(section_ids)
    latest_semester_labels = _transcript_latest_semester_labels(page_grades)
    rows: list[GradeTranscriptSummaryRowT] = []
    for student in students:
        stats = grade_stats.get(student.id, {"grade_count": 0, "section_count": 0})
        rows.append(
            {
                "student": student,
                "student_label": _student_label(student),
                "student_id": student.student_id or str(student.id),
                "grade_count": stats["grade_count"],
                "section_count": stats["section_count"],
                "latest_semester_label": latest_semester_labels.get(student.id, ""),
                "detail_url": reverse(
                    "staff_grade_transcript",
                    args=[role_slug, student.id],
                ),
            }
        )

    role_title = _role_title(role_slug)
    pagination_query, pagination_hidden_fields = _pagination_hidden_fields(request.GET)
    return {
        "page_title": f"{role_title} grade transcripts",
        "page_summary": "Transcript previews for students with grades in your course scope.",
        "eyebrow": role_slug.replace("_", " ").title(),
        "sidebar_links": build_staff_sidebar_links(role_slug, "grade_transcripts"),
        "role_switcher": build_staff_role_switcher(user, role_slug),
        "breadcrumbs": _transcript_breadcrumbs(role_slug, ""),
        "dashboard_url": reverse("staff_role_dashboard", args=[role_slug]),
        "role_slug": role_slug,
        "scope_label": _scope_label(user, role_slug),
        "student_autocomplete_url": reverse(
            "staff_grade_transcript_student_autocomplete",
            args=[role_slug],
        ),
        "semester_options": _semester_options(semester_id),
        "selected_student_id": selected_student_id,
        "selected_student_label": _student_filter_label(selected_student_id),
        "student_page": student_page,
        "transcript_rows": rows,
        "pagination_query": pagination_query,
        "pagination_hidden_fields": pagination_hidden_fields,
        "pagination_action": request.path,
    }


def _require_student_in_transcript_scope(
    user: User,
    role_slug: str,
    student_id: int,
) -> Student:
    """Return a student only when a scoped course grade makes them visible."""
    student = get_object_or_404(Student.objects.select_related("user"), pk=student_id)
    scoped_section_ids = scoped_grade_roster_sections(user, role_slug).values_list(
        "id",
        flat=True,
    )
    # Academic transcript visibility is granted by scoped course-grade evidence.
    if not Grade.objects.filter(
        student_id=student.id,
        section_id__in=scoped_section_ids,
    ).exists():
        raise Http404("No transcript grades are visible in this role scope.")
    return student


def build_grade_transcript_context(
    request: HttpRequest,
    role_slug: str,
    student_id: int,
) -> PortalContextT:
    """Build one scoped academic transcript preview."""
    user = _as_user(request.user)
    student = _require_student_in_transcript_scope(user, role_slug, student_id)
    transcript = build_transcript_document(student.id)
    return {
        "page_title": "Grade transcript",
        "page_summary": "Academic oversight transcript preview.",
        "eyebrow": role_slug.replace("_", " ").title(),
        "std_label": transcript["student_name"],
        "curriculum_label": transcript["major_program"],
        "generated_at": transcript["printed_date"],
        "transcript": transcript,
        "transcript_rows": flatten_transcript_rows(transcript),
        "sidebar_links": build_staff_sidebar_links(role_slug, "grade_transcripts"),
        "role_switcher": build_staff_role_switcher(user, role_slug),
        "breadcrumbs": _transcript_breadcrumbs(role_slug, transcript["student_name"]),
        "dashboard_url": reverse("staff_grade_transcripts", args=[role_slug]),
        "back_label": "Back to transcripts",
    }


def _oversight_breadcrumbs(role_slug: str, label: str) -> list[BreadcrumbT]:
    """Return breadcrumbs rooted in the active oversight workspace."""
    crumbs: list[BreadcrumbT] = [
        {
            "label": _role_title(role_slug),
            "href": reverse("staff_role_dashboard", args=[role_slug]),
        },
        {
            "label": "Grade rosters",
            "href": reverse("staff_grade_rosters", args=[role_slug]),
        },
    ]
    if label:
        crumbs.append({"label": label, "href": ""})
    else:
        crumbs[-1]["href"] = ""
    return crumbs


def _transcript_breadcrumbs(role_slug: str, label: str) -> list[BreadcrumbT]:
    """Return breadcrumbs rooted in the scoped transcript workspace."""
    crumbs: list[BreadcrumbT] = [
        {
            "label": _role_title(role_slug),
            "href": reverse("staff_role_dashboard", args=[role_slug]),
        },
        {
            "label": "Grade transcripts",
            "href": reverse("staff_grade_transcripts", args=[role_slug]),
        },
    ]
    if label:
        crumbs.append({"label": label, "href": ""})
    else:
        crumbs[-1]["href"] = ""
    return crumbs


def oversight_student_results(
    user: User,
    role_slug: str,
    query: str | None,
) -> list[AutocompleteResultT]:
    """Return student suggestions limited to the current oversight scope."""
    clean_query = parse_str(query)
    if not clean_query:
        return []
    section_ids = scoped_grade_roster_sections(user, role_slug).values_list(
        "id",
        flat=True,
    )
    student_qs = (
        Student.objects.select_related("user")
        .filter(student_registrations__section_id__in=section_ids)
        .filter(
            Q(student_id__icontains=clean_query)
            | Q(long_name__icontains=clean_query)
            | Q(user__first_name__icontains=clean_query)
            | Q(user__last_name__icontains=clean_query)
            | Q(user__username__icontains=clean_query)
        )
        .distinct()
        .order_by("long_name", "student_id")[:15]
    )
    return [
        {"id": student.id, "text": f"{student.student_id} - {_student_label(student)}"}
        for student in student_qs
    ]


def oversight_transcript_student_results(
    user: User,
    role_slug: str,
    query: str | None,
) -> list[AutocompleteResultT]:
    """Return transcript student suggestions limited by scoped grade rows."""
    clean_query = parse_str(query)
    if not clean_query:
        return []
    scoped_grade_students = _filtered_transcript_grades(
        user,
        role_slug,
        QueryDict(mutable=True),
    ).values_list("student_id", flat=True)
    student_qs = (
        Student.objects.select_related("user")
        .filter(id__in=scoped_grade_students)
        .filter(
            Q(student_id__icontains=clean_query)
            | Q(long_name__icontains=clean_query)
            | Q(user__first_name__icontains=clean_query)
            | Q(user__last_name__icontains=clean_query)
            | Q(user__username__icontains=clean_query)
        )
        .distinct()
        .order_by("long_name", "student_id")[:15]
    )
    return [
        {"id": student.id, "text": f"{student.student_id} - {_student_label(student)}"}
        for student in student_qs
    ]


def oversight_faculty_results(
    user: User,
    role_slug: str,
    query: str | None,
) -> list[AutocompleteResultT]:
    """Return faculty suggestions limited to the current oversight scope."""
    clean_query = parse_str(query)
    if not clean_query:
        return []
    faculty_ids = (
        scoped_grade_roster_sections(user, role_slug)
        .exclude(faculty__isnull=True)
        .values_list("faculty_id", flat=True)
        .distinct()
    )
    faculty_qs = (
        Faculty.objects.select_related(
            "staff_profile__user",
            "staff_profile__department",
            "college",
        )
        .filter(id__in=faculty_ids)
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
    return [
        {"id": faculty.id, "text": _faculty_filter_label(faculty)}
        for faculty in faculty_qs
    ]


__all__ = [
    "OVERSIGHT_ROLE_SLUGS",
    "build_grade_transcript_context",
    "build_grade_transcript_list_context",
    "build_grade_roster_detail_context",
    "build_grade_roster_list_context",
    "oversight_faculty_results",
    "oversight_student_results",
    "oversight_transcript_student_results",
    "scoped_grade_roster_sections",
]
