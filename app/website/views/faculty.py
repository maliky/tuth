"""Faculty-facing grade-entry views."""

from __future__ import annotations

from typing import cast

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from app.website.services.faculty_grade_csv import (
    FacultyGradeCsvError,
    grade_roster_csv,
    import_grade_roster_csv,
)
from app.website.services.faculty_grade_portal import (
    FacultyGradeError,
    build_faculty_grade_roster_context,
    build_faculty_grade_sections_context,
    get_faculty_section_or_404,
    save_grade_autosave,
    save_grade_roster,
)


@login_required
def faculty_grade_sections(request: HttpRequest) -> HttpResponse:
    """Render the faculty section list used for grade entry."""
    context = build_faculty_grade_sections_context(request)
    return render(request, "website/staff/faculty_grade_sections.html", context)


@login_required
def faculty_grade_roster(request: HttpRequest, section_id: int) -> HttpResponse:
    """Render and process one faculty grade roster."""
    user = cast(User, request.user)
    section = get_faculty_section_or_404(user, section_id)
    if request.method == "POST":
        try:
            changed = save_grade_roster(section, request.POST)
        except FacultyGradeError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"{changed} grade row(s) saved.")
        return redirect("faculty_grade_roster", section_id=section.id)

    context = build_faculty_grade_roster_context(request, section.id)
    return render(request, "website/staff/faculty_grade_roster.html", context)


@login_required
@require_POST
def faculty_grade_roster_autosave(
    request: HttpRequest,
    section_id: int,
) -> JsonResponse:
    """Save one faculty grade value from the roster autosave control."""
    try:
        grade_id = int(request.POST.get("grade_id", ""))
    except ValueError:
        return JsonResponse({"ok": False, "error": "Invalid grade row."}, status=400)

    try:
        grade = save_grade_autosave(
            cast(User, request.user),
            section_id,
            grade_id,
            request.POST.get("grade_code", ""),
        )
    except FacultyGradeError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=403)

    grade_code = grade.value.code.upper() if grade.value else ""
    return JsonResponse({"ok": True, "grade_code": grade_code})


@login_required
def faculty_grade_roster_download(
    request: HttpRequest,
    section_id: int,
) -> HttpResponse:
    """Download a CSV grade roster for one assigned section."""
    section = get_faculty_section_or_404(cast(User, request.user), section_id)
    csv_text = grade_roster_csv(section)
    filename = f"grade_roster_section_{section.id}.csv"
    response = HttpResponse(csv_text, content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
@require_POST
def faculty_grade_roster_upload(
    request: HttpRequest,
    section_id: int,
) -> HttpResponse:
    """Import a faculty CSV grade roster for one assigned section."""
    section = get_faculty_section_or_404(cast(User, request.user), section_id)
    uploaded_file = request.FILES.get("roster_file")
    if uploaded_file is None:
        messages.error(request, "Choose a CSV roster file to upload.")
        return redirect("faculty_grade_roster", section_id=section.id)
    try:
        changed = import_grade_roster_csv(section, uploaded_file)
    except FacultyGradeCsvError as exc:
        context = build_faculty_grade_roster_context(request, section.id)
        context["upload_error_summary"] = exc.summary
        context["upload_errors"] = exc.issues
        return render(
            request,
            "website/staff/faculty_grade_roster.html",
            context,
            status=400,
        )
    except FacultyGradeError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"{changed} grade row(s) imported.")
    return redirect("faculty_grade_roster", section_id=section.id)


__all__ = [
    "faculty_grade_roster",
    "faculty_grade_roster_autosave",
    "faculty_grade_roster_download",
    "faculty_grade_roster_upload",
    "faculty_grade_sections",
]
