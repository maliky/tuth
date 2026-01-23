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

from app.people.models.student import Student
from app.registry.models.grade import Grade
from app.shared.admin.core import get_current_semester
from app.shared.utils import parse_str
from app.timetable.models.semester import Semester, SemesterStatus


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


class RegistrarStudentGroupT(TypedDict):
    """Grouped grade rows for a student."""

    student: Student
    student_label: str
    student_id: str
    semesters: list[RegistrarSemesterGroupT]


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
    search_query = parse_str(request.GET.get("q"))
    selected_student_id = _clean_int(request.GET.get("student_id"))
    semester_param = request.GET.get("semester")
    semester_id = _clean_int(semester_param)
    semester_param_present = "semester" in request.GET
    if semester_param == "all":
        semester_id = None
    if not semester_param_present:
        current_semester = get_current_semester()
        if current_semester:
            semester_id = current_semester.id

    grades_qs = Grade.objects.select_related(
        "student",
        "student__user",
        "section__semester__academic_year",
        "section__curriculum_course__course",
        "section__curriculum_course__credit_hours",
        "section__faculty__staff_profile__user",
        "value",
    ).order_by(
        "student__long_name",
        "-section__semester__start_date",
        "-section__semester__number",
        "section__curriculum_course__course__short_code",
    )

    if semester_id:
        grades_qs = grades_qs.filter(section__semester_id=semester_id)
    if selected_student_id:
        grades_qs = grades_qs.filter(student_id=selected_student_id)
    if search_query:
        grades_qs = grades_qs.filter(
            Q(student__student_id__icontains=search_query)
            | Q(student__long_name__icontains=search_query)
            | Q(student__user__first_name__icontains=search_query)
            | Q(student__user__last_name__icontains=search_query)
            | Q(section__curriculum_course__course__short_code__icontains=search_query)
            | Q(section__curriculum_course__course__title__icontains=search_query)
            | Q(section__faculty__staff_profile__user__first_name__icontains=search_query)
            | Q(section__faculty__staff_profile__user__last_name__icontains=search_query)
        )

    per_page = 100
    paginator = Paginator(grades_qs, per_page)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    student_groups: list[RegistrarStudentGroupT] = []
    student_lookup: dict[int, RegistrarStudentGroupT] = {}
    semester_lookup_map: dict[int, dict[int, RegistrarSemesterGroupT]] = {}
    for grade in page_obj:
        student = grade.student
        student_group = student_lookup.get(student.id)
        if student_group is None:
            student_group = cast(
                RegistrarStudentGroupT,
                {
                    "student": student,
                    "student_label": student.long_name or student.user.get_full_name(),
                    "student_id": student.student_id or "Pending ID",
                    "semesters": [],
                },
            )
            student_lookup[student.id] = student_group
            student_groups.append(student_group)
            semester_lookup_map[student.id] = cast(dict[int, RegistrarSemesterGroupT], {})
        assert student_group is not None
        semester_group_lookup = semester_lookup_map[student.id]
        semester = grade.section.semester
        semester_group = semester_group_lookup.get(semester.id)
        if semester_group is None:
            semester_group = cast(
                RegistrarSemesterGroupT,
                {
                    "semester": semester,
                    "label": (
                        f"{semester.academic_year.code} · Semester {semester.number}"
                    ),
                    "rows": [],
                },
            )
            semester_group_lookup[semester.id] = semester_group
            student_group["semesters"].append(semester_group)
        assert semester_group is not None
        faculty_label = "TBA"
        if grade.section.faculty and grade.section.faculty.staff_profile:
            faculty_label = (
                grade.section.faculty.staff_profile.user.get_full_name()
                or str(grade.section.faculty.staff_profile)
            )
        course = grade.section.curriculum_course.course
        course_code = course.short_code or course.code or ""
        course_title = course.title or ""
        grade_label = "-"
        if grade.value and grade.value.code:
            grade_label = grade.value.code.upper()
        semester_group["rows"].append(
            {
                "course_code": course_code,
                "course_title": course_title,
                "credits": int(grade.section.curriculum_course.credit_hours.code),
                "grade": grade_label,
                "faculty": faculty_label,
            }
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

    context = {
        "page_title": "Registrar grades",
        "page_summary": "Review grades grouped by student and semester.",
        "eyebrow": "Registrar",
        "search_query": search_query,
        "student_groups": student_groups,
        "page_obj": page_obj,
        "semester_options": semester_options,
        "selected_student_id": selected_student_id,
        "selected_student_label": selected_student_label,
        "student_autocomplete_url": reverse("registrar_student_autocomplete"),
    }
    return render(request, "website/staff/registrar_grades_dashboard.html", context)


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
