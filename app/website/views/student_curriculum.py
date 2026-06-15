"""Student curriculum overview views."""

from __future__ import annotations

from typing import TypedDict

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render

from app.academics.models.curriculum_course import CurriCrs
from app.website.services.student_course_info import build_student_course_info

from .student_helpers import (
    _build_sidebar_links,
    _build_std_profile,
    _require_std,
)


class CurriCrsRowT(TypedDict):
    """Row details for curriculum course listings."""

    id: int
    code: str
    title: str
    credits: int


@login_required
def std_curri_crss(request: HttpRequest) -> HttpResponse:
    """Render an ordered list of curriculum courses for the current student."""
    student = _require_std(request.user)
    curriculum = student.primary_curriculum
    curriculum_courses = (
        CurriCrs.objects.filter(curriculum=curriculum)
        .select_related("course", "credit_hours")
        .order_by("course__short_code", "course__code")
    )
    course_rows: list[CurriCrsRowT] = [
        {
            "id": cc.id,
            "code": cc.course.short_code or cc.course.code or "",
            "title": cc.course.title or "",
            "credits": int(cc.credit_hours.code),
        }
        for cc in curriculum_courses
    ]
    context = {
        "student_profile": _build_std_profile(student),
        "sidebar_links": _build_sidebar_links("Course Registration", student=student),
        "course_rows": course_rows,
        "curriculum_label": curriculum.long_name or curriculum.short_name,
    }
    return render(request, "website/student_curriculum_courses.html", context)


@login_required
def std_curri_crs_detail(
    request: HttpRequest,
    curriculum_course_id: int,
) -> HttpResponse:
    """Render course details for a curriculum course linked to the student."""
    student = _require_std(request.user)
    curriculum = student.primary_curriculum
    curriculum_course = (
        CurriCrs.objects.filter(
            curriculum=curriculum,
            pk=curriculum_course_id,
        )
        .select_related("course", "credit_hours", "curriculum")
        .prefetch_related("requirement_groups__members__required_course")
        .first()
    )
    if curriculum_course is None:
        raise Http404("Course not found.")

    course_info = build_student_course_info(
        student=student,
        curriculum_course=curriculum_course,
    )
    context = {
        "student_profile": _build_std_profile(student),
        "sidebar_links": _build_sidebar_links("Course Registration", student=student),
        "course": course_info,
        "course_info": course_info,
    }
    return render(
        request,
        "website/student_curriculum_course_detail.html",
        context,
    )
