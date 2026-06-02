"""Registrar-specific views."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render

from app.website.services.registrar_portal import (
    build_reg_grade_transcript_context,
    build_reg_grades_context,
    build_reg_windows_context,
    registrar_student_results,
    update_semester_window,
)


@login_required
@permission_required("registry.view_grade", raise_exception=True)
def reg_std_autocomplete(request: HttpRequest) -> HttpResponse:
    """Return student suggestions for the registrar grade dashboard."""
    return JsonResponse({"results": registrar_student_results(request.GET.get("q"))})


@login_required
@permission_required("registry.view_grade", raise_exception=True)
def reg_grades_dashboard(request: HttpRequest) -> HttpResponse:
    """Render the registrar grade dashboard grouped by student and semester."""
    context = build_reg_grades_context(request)
    return render(request, "website/staff/registrar_grades_dashboard.html", context)


@login_required
@permission_required("registry.view_grade", raise_exception=True)
def reg_grade_transcript(
    request: HttpRequest,
    student_id: int,
) -> HttpResponse:
    """Render an official grade transcript preview for a student."""
    context = build_reg_grade_transcript_context(request, student_id)
    return render(request, "website/staff/registrar_grade_transcript.html", context)


@permission_required("timetable.change_semester", raise_exception=True)
def reg_crs_wins(request: HttpRequest) -> HttpResponse:
    """Allow registrar staff to manage semester statuses."""
    if request.method == "POST":
        try:
            msg = update_semester_window(
                request.POST.get("semester_id"),
                request.POST.get("status_code"),
            )
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("reg_crs_wins")
        messages.success(request, msg)
        return redirect("reg_crs_wins")

    context = build_reg_windows_context(request)
    return render(request, "website/registrar_windows.html", context)
