"""Student curriculum overview views."""

from __future__ import annotations

from typing import TypedDict

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render

from app.academics.models.course import CurriculumCourse

from .student_helpers import (
    _build_sidebar_links,
    _build_student_profile,
    _require_student,
)


class CurriculumCourseRowT(TypedDict):
    """Row details for curriculum course listings."""

    id: int
    code: str
    title: str
    credits: int


class CurriculumCourseDetailT(TypedDict):
    """Detail data for a curriculum course."""

    code: str
    title: str
    credits: int
    description: str
    curriculum_label: str


@login_required
def student_curriculum_courses(request: HttpRequest) -> HttpResponse:
    """Render an ordered list of curriculum courses for the current student."""
    student = _require_student(request.user)
    curriculum_courses = (
        CurriculumCourse.objects.filter(curriculum=student.curriculum)
        .select_related("course", "credit_hours")
        .order_by("course__short_code", "course__code")
    )
    course_rows: list[CurriculumCourseRowT] = [
        {
            "id": cc.id,
            "code": cc.course.short_code or cc.course.code or "",
            "title": cc.course.title or "",
            "credits": int(cc.credit_hours.code),
        }
        for cc in curriculum_courses
    ]
    context = {
        "student_profile": _build_student_profile(student),
        "sidebar_links": _build_sidebar_links("Course Registration", student=student),
        "course_rows": course_rows,
        "curriculum_label": student.curriculum.long_name or student.curriculum.short_name,
    }
    return render(request, "website/student_curriculum_courses.html", context)


@login_required
def student_curriculum_course_detail(
    request: HttpRequest,
    curriculum_course_id: int,
) -> HttpResponse:
    """Render course details for a curriculum course linked to the student."""
    student = _require_student(request.user)
    curriculum_course = (
        CurriculumCourse.objects.filter(
            curriculum=student.curriculum,
            pk=curriculum_course_id,
        )
        .select_related("course", "credit_hours", "curriculum")
        .first()
    )
    if curriculum_course is None:
        raise Http404("Course not found.")

    course = curriculum_course.course
    course_detail: CurriculumCourseDetailT = {
        "code": course.short_code or course.code or "",
        "title": course.title or "",
        "credits": int(curriculum_course.credit_hours.code),
        "description": course.description or "No description available.",
        "curriculum_label": str(curriculum_course.curriculum),
    }
    context = {
        "student_profile": _build_student_profile(student),
        "sidebar_links": _build_sidebar_links("Course Registration", student=student),
        "course": course_detail,
    }
    return render(
        request,
        "website/student_curriculum_course_detail.html",
        context,
    )
