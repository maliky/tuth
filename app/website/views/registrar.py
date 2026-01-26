"""Registrar-specific views."""

from __future__ import annotations

from typing import TypedDict, cast

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from app.people.models.student import Student
from app.registry.models.grade import Grade
from app.shared.utils import parse_str
from app.timetable.models.semester import Semester, SemesterStatus
from app.timetable.utils import format_datetime


class RegistrarGradeRowT(TypedDict):
    """Details for a registrar grade row."""

    course_code: str
    course_title: str
    credits: int
    grade: str
    faculty: str


class RegistrarSemesterGroupT(TypedDict):
    """Grouped grade rows for a semester."""

    semester: Semester
    label: str
    rows: list[RegistrarGradeRowT]
    credits_total: int
    gpa: str


class RegistrarStudentGroupT(TypedDict):
    """Grouped grade rows for a student."""

    student: Student
    student_label: str
    student_id: str
    semesters: list[RegistrarSemesterGroupT]
    credits_total: int
    gpa: str


class RegistrarTranscriptRowT(TypedDict):
    """Row details for the official grade transcript."""

    semester_label: str
    course_code: str
    course_title: str
    credits: int
    grade: str


GPA_EXCLUDED_CODES = {"ip", "ng", "w", "i", "ab", "dr"}


def _clean_int(value: str | None) -> int | None:
    """Return a cleaned integer or None."""
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


@login_required
@permission_required("registry.view_grade", raise_exception=True)
def registrar_student_autocomplete(request: HttpRequest) -> HttpResponse:
    """Return student suggestions for the registrar grade dashboard."""
    query = parse_str(request.GET.get("q"))
    if not query:
        return JsonResponse({"results": []})
    students = (
        Student.objects.select_related("user")
        .filter(
            Q(student_id__icontains=query)
            | Q(long_name__icontains=query)
            | Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(user__username__icontains=query)
        )
        .order_by("long_name")[:15]
    )
    results = [
        {
            "id": student.id,
            "text": f"{student.student_id} — {student.long_name}",
        }
        for student in students
    ]
    return JsonResponse({"results": results})


@login_required
@permission_required("registry.view_grade", raise_exception=True)
def registrar_grades_dashboard(request: HttpRequest) -> HttpResponse:
    """Render the registrar grade dashboard grouped by student and semester."""
    selected_student_id = _clean_int(request.GET.get("student_id"))
    semester_param = request.GET.get("semester")
    semester_id = _clean_int(semester_param)
    semester_param_present = "semester" in request.GET
    if semester_param == "all":
        semester_id = None
    if not semester_param_present:
        # Keep the default selection aligned with shared semester rules.
        current_semester = Semester.get_current_semester()
        if current_semester:
            semester_id = current_semester.id

    students_qs = Student.objects.filter(grade__isnull=False).select_related("user")
    if semester_id:
        students_qs = students_qs.filter(grade__section__semester_id=semester_id)
    if selected_student_id:
        students_qs = students_qs.filter(id=selected_student_id)
    students_qs = students_qs.distinct().order_by("long_name", "student_id")

    per_page = 100
    paginator = Paginator(students_qs, per_page)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

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

    student_groups: list[RegistrarStudentGroupT] = []
    student_lookup: dict[int, RegistrarStudentGroupT] = {}
    semester_lookup_map: dict[int, dict[int, RegistrarSemesterGroupT]] = {}
    student_gpa_points: dict[int, float] = {}
    student_gpa_credits: dict[int, int] = {}
    semester_gpa_points: dict[tuple[int, int], float] = {}
    semester_gpa_credits: dict[tuple[int, int], int] = {}
    for student in page_obj:
        student_group = cast(
            RegistrarStudentGroupT,
            {
                "student": student,
                "student_label": student.long_name or student.user.get_full_name(),
                "student_id": student.student_id or "Pending ID",
                "semesters": [],
                "credits_total": 0,
                "gpa": "N/A",
            },
        )
        student_groups.append(student_group)
        student_lookup[student.id] = student_group
        semester_lookup_map[student.id] = {}
        student_gpa_points[student.id] = 0.0
        student_gpa_credits[student.id] = 0

    for grade in grades_qs:
        student = grade.student
        student_group_opt = student_lookup.get(student.id)
        if student_group_opt is None:
            continue
        student_group = student_group_opt
        semester_group_lookup = semester_lookup_map[student.id]
        semester = grade.section.semester
        semester_group_opt = semester_group_lookup.get(semester.id)
        if semester_group_opt is None:
            semester_group = cast(
                RegistrarSemesterGroupT,
                {
                    "semester": semester,
                    "label": (
                        f"{semester.academic_year.code} · Semester {semester.number}"
                    ),
                    "rows": [],
                    "credits_total": 0,
                    "gpa": "N/A",
                },
            )
            semester_group_lookup[semester.id] = semester_group
            student_group["semesters"].append(semester_group)
            semester_gpa_points[(student.id, semester.id)] = 0.0
            semester_gpa_credits[(student.id, semester.id)] = 0
        else:
            semester_group = semester_group_opt
        faculty_label = "TBA"
        if grade.section.faculty and grade.section.faculty.staff_profile:
            faculty_label = (
                grade.section.faculty.staff_profile.user.get_full_name()
                or str(grade.section.faculty.staff_profile)
            )
        course = grade.section.curriculum_course.course
        course_code = course.short_code or course.code or ""
        course_title = course.title or ""
        credits = int(grade.section.curriculum_course.credit_hours.code)
        grade_label = "-"
        if grade.value and grade.value.code:
            grade_label = grade.value.code.upper()
        semester_group["rows"].append(
            {
                "course_code": course_code,
                "course_title": course_title,
                "credits": credits,
                "grade": grade_label,
                "faculty": faculty_label,
            }
        )
        semester_group["credits_total"] += credits
        student_group["credits_total"] += credits
        if (
            grade.value
            and grade.value.number is not None
            and (grade.value.code or "").lower() not in GPA_EXCLUDED_CODES
        ):
            semester_key = (student.id, semester.id)
            semester_gpa_points[semester_key] = (
                semester_gpa_points.get(semester_key, 0.0)
                + float(grade.value.number) * credits
            )
            semester_gpa_credits[semester_key] = (
                semester_gpa_credits.get(semester_key, 0) + credits
            )
            student_gpa_points[student.id] = (
                student_gpa_points.get(student.id, 0.0)
                + float(grade.value.number) * credits
            )
            student_gpa_credits[student.id] = (
                student_gpa_credits.get(student.id, 0) + credits
            )

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

    semester_options = [
        {"value": "all", "label": "All semesters", "selected": semester_param == "all"}
    ]
    for sem in Semester.objects.select_related("academic_year").order_by(
        "-academic_year__start_date",
        "-number",
    ):
        semester_options.append(
            {
                "value": str(sem.id),
                "label": f"{sem.academic_year.code} · Semester {sem.number}",
                "selected": semester_id == sem.id,
            }
        )

    selected_student_label = ""
    if selected_student_id:
        selected_student = Student.objects.filter(id=selected_student_id).first()
        if selected_student:
            selected_student_label = (
                selected_student.long_name
                or selected_student.user.get_full_name()
                or selected_student.student_id
            )

    pagination_params = request.GET.copy()
    pagination_params.pop("page", None)
    if "semester" not in pagination_params and semester_id:
        pagination_params["semester"] = str(semester_id)
    if selected_student_id and "student_id" not in pagination_params:
        pagination_params["student_id"] = str(selected_student_id)
    # Preserve filter inputs when the "Go to page" form submits.
    pagination_hidden_fields: list[dict[str, str]] = []
    for key, values in pagination_params.lists():
        for value in values:
            pagination_hidden_fields.append({"name": key, "value": value})

    context = {
        "page_title": "Registrar grades",
        "page_summary": "Review grades grouped by student and semester.",
        "eyebrow": "Registrar",
        "student_groups": student_groups,
        "page_obj": page_obj,
        "semester_options": semester_options,
        "selected_student_id": selected_student_id,
        "selected_student_label": selected_student_label,
        "pagination_query": pagination_params.urlencode(),
        "pagination_hidden_fields": pagination_hidden_fields,
        "pagination_action": request.path,
        "student_autocomplete_url": reverse("registrar_student_autocomplete"),
    }
    return render(request, "website/staff/registrar_grades_dashboard.html", context)


@login_required
@permission_required("registry.view_grade", raise_exception=True)
def registrar_grade_transcript(
    request: HttpRequest,
    student_id: int,
) -> HttpResponse:
    """Render an official grade transcript preview for a student."""
    student = get_object_or_404(
        Student.objects.select_related("user", "curriculum"), pk=student_id
    )
    grades = (
        Grade.objects.select_related(
            "section__semester__academic_year",
            "section__curriculum_course__course",
            "section__curriculum_course__credit_hours",
            "value",
        )
        .filter(student=student)
        .order_by(
            "section__semester__start_date",
            "section__semester__number",
            "section__curriculum_course__course__short_code",
        )
    )
    transcript_rows: list[RegistrarTranscriptRowT] = []
    for grade in grades:
        semester = grade.section.semester
        course = grade.section.curriculum_course.course
        grade_label = "-"
        if grade.value and grade.value.code:
            grade_label = grade.value.code.upper()
        transcript_rows.append(
            {
                "semester_label": (
                    f"{semester.academic_year.code} · Semester {semester.number}"
                ),
                "course_code": course.short_code or course.code or "",
                "course_title": course.title or "",
                "credits": int(grade.section.curriculum_course.credit_hours.code),
                "grade": grade_label,
            }
        )
    context = {
        "page_title": "Official grade transcript",
        "page_summary": "Registrar-issued transcript preview.",
        "eyebrow": "Registrar",
        "student": student,
        "student_label": (
            student.long_name or student.user.get_full_name() or student.student_id
        ),
        "curriculum_label": (
            student.curriculum.long_name or student.curriculum.short_name
        ),
        "generated_at": format_datetime(timezone.now()),
        "transcript_rows": transcript_rows,
        "dashboard_url": reverse("registrar_grades_dashboard"),
    }
    return render(request, "website/staff/registrar_grade_transcript.html", context)


@permission_required("timetable.change_semester", raise_exception=True)
def registrar_course_windows(request: HttpRequest) -> HttpResponse:
    """Allow registrar staff to manage semester statuses."""
    semesters = (
        Semester.objects.select_related("academic_year", "status")
        .order_by("-academic_year__start_date", "-number")
        .all()
    )
    statuses = SemesterStatus.objects.all().order_by("code")

    if request.method == "POST":
        semester_id = request.POST.get("semester_id")
        status_code = request.POST.get("status_code")
        semester = get_object_or_404(Semester, pk=semester_id)
        if status_code not in {status.code for status in statuses}:
            messages.error(request, "Unknown status.")
            return redirect("registrar_course_windows")
        semester.status_id = status_code
        semester.save(update_fields=["status"])
        messages.success(
            request,
            f"{semester} status updated to {semester.status.label}.",
        )
        return redirect("registrar_course_windows")

    context = {
        "semesters": semesters,
        "statuses": statuses,
        "page_title": "Course selection windows",
        "page_summary": "Open or close registration periods directly from Tusis.",
        "breadcrumbs": [
            {"label": "Registrar desk", "href": ""},
        ],
    }
    return render(request, "website/registrar_windows.html", context)
