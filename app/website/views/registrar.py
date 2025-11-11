"""Registrar-specific views."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from app.timetable.models.semester import Semester, SemesterStatus


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

    return render(
        request,
        "website/registrar_windows.html",
        {"semesters": semesters, "statuses": statuses},
    )
