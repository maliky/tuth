"""Registrar-specific views."""

from __future__ import annotations

from io import BytesIO
from typing import cast
from zipfile import ZIP_DEFLATED, ZipFile

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from app.people.models.student import Student
from app.shared.auth.perms import UserRole
from app.website.services.registrar_portal import (
    build_reg_grade_transcript_context,
    build_reg_grades_context,
    build_reg_windows_context,
    clean_int,
    registrar_student_results,
    update_semester_window,
)
from app.website.services.registrar_rosters import (
    build_reg_class_roster_detail_context,
    build_reg_class_roster_list_context,
    registrar_faculty_results,
)
from app.website.services.transcript_document import build_transcript_document
from app.website.services.transcript_artifacts import issue_transcript_artifact
from app.website.services.transcript_rendering import (
    render_transcript_document_org,
)
from app.website.services.transcript_types import (
    TranscriptLayoutKeyT,
    normalize_transcript_layout,
)

REGISTRAR_TRANSCRIPT_ROLE_LABELS = frozenset(
    {
        UserRole.REGISTRAR.value.label,
        UserRole.REGISTRAR_OFFICER.value.label,
    }
)


def _int_values(values: list[str]) -> list[int]:
    """Return valid integer ids from a posted multi-value field."""
    clean_values: list[int] = []
    for value in values:
        clean_value = clean_int(value)
        if clean_value is not None:
            clean_values.append(clean_value)
    return clean_values


def _transcript_layout_from_request(request: HttpRequest) -> TranscriptLayoutKeyT:
    """Return the requested transcript layout, falling back to the default."""
    raw_layout = request.POST.get("layout") if request.method == "POST" else None
    if raw_layout is None:
        raw_layout = request.GET.get("layout")
    if raw_layout is None:
        raw_layout = request.GET.get("orientation")
    return normalize_transcript_layout(raw_layout)


def _bulk_transcript_students(request: HttpRequest) -> list[Student]:
    """Return students selected for a bulk transcript export."""
    student_ids = _int_values(request.POST.getlist("student_ids"))
    if not student_ids:
        raise ValueError("Select at least one student transcript.")
    return list(
        Student.objects.filter(id__in=student_ids, grade__isnull=False)
        .distinct()
        .order_by("long_name", "student_id")
    )


def _require_transcript_export_access(request: HttpRequest) -> None:
    """Raise unless the user is a registrar actor allowed to export transcripts."""
    user = cast(User, request.user)
    if not user.groups.filter(name__in=REGISTRAR_TRANSCRIPT_ROLE_LABELS).exists():
        raise PermissionDenied


def _require_registrar_roster_access(request: HttpRequest) -> None:
    """Raise unless the user belongs to a registrar roster-review role."""
    user = cast(User, request.user)
    if user.is_superuser:
        return
    if not user.groups.filter(name__in=REGISTRAR_TRANSCRIPT_ROLE_LABELS).exists():
        raise PermissionDenied


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
def reg_class_rosters(request: HttpRequest) -> HttpResponse:
    """Render read-only class roster summaries for registrar staff."""
    _require_registrar_roster_access(request)
    context = build_reg_class_roster_list_context(request)
    return render(request, "website/staff/registrar_class_rosters.html", context)


@login_required
@permission_required("registry.view_grade", raise_exception=True)
def reg_class_roster_detail(
    request: HttpRequest,
    section_id: int,
) -> HttpResponse:
    """Render one read-only class roster for registrar staff."""
    _require_registrar_roster_access(request)
    context = build_reg_class_roster_detail_context(request, section_id)
    return render(request, "website/staff/registrar_class_roster_detail.html", context)


@login_required
@permission_required("registry.view_grade", raise_exception=True)
def reg_faculty_autocomplete(request: HttpRequest) -> HttpResponse:
    """Return faculty suggestions for registrar class roster filters."""
    _require_registrar_roster_access(request)
    return JsonResponse({"results": registrar_faculty_results(request.GET.get("q"))})


@login_required
@permission_required("registry.view_grade", raise_exception=True)
def reg_grade_transcript(
    request: HttpRequest,
    student_id: int,
) -> HttpResponse:
    """Render an official grade transcript preview for a student."""
    context = build_reg_grade_transcript_context(request, student_id)
    return render(request, "website/staff/registrar_grade_transcript.html", context)


@login_required
@permission_required("registry.view_grade", raise_exception=True)
def reg_grade_transcript_pdf(
    request: HttpRequest,
    student_id: int,
) -> HttpResponse:
    """Generate and download the registrar transcript PDF."""
    _require_transcript_export_access(request)
    layout_key = _transcript_layout_from_request(request)
    artifact = issue_transcript_artifact(
        request,
        layout=layout_key,
        student_id=student_id,
    )
    response = HttpResponse(artifact.pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{artifact.filename}"'
    return response


@login_required
@permission_required("registry.view_grade", raise_exception=True)
@require_POST
def reg_grade_transcripts_bulk_pdf(request: HttpRequest) -> HttpResponse:
    """Generate and download a ZIP of registrar transcript PDFs."""
    _require_transcript_export_access(request)
    try:
        students = _bulk_transcript_students(request)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("reg_grades_dashboard")
    if not students:
        messages.error(request, "No transcript students matched the export request.")
        return redirect("reg_grades_dashboard")

    layout_key = _transcript_layout_from_request(request)
    timestamp = timezone.now().strftime("%Y%m%d_%H%M")
    archive_buffer = BytesIO()
    with ZipFile(archive_buffer, "w", ZIP_DEFLATED) as archive:
        for student in students:
            artifact = issue_transcript_artifact(
                request,
                layout=layout_key,
                student_id=student.id,
            )
            archive.writestr(
                artifact.filename,
                artifact.pdf_bytes,
            )

    filename = f"transcripts_{layout_key}_{timestamp}.zip"
    response = HttpResponse(archive_buffer.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
@permission_required("registry.view_grade", raise_exception=True)
def reg_grade_transcript_org(
    request: HttpRequest,
    student_id: int,
) -> HttpResponse:
    """Generate and download the registrar transcript Org source."""
    _require_transcript_export_access(request)
    transcript = build_transcript_document(student_id)
    org_source = render_transcript_document_org(transcript)
    org_bytes = org_source.encode("utf-8")
    timestamp = timezone.now().strftime("%Y%m%d_%H%M")
    filename = f"transcript_{transcript['student_id']}_{timestamp}.org"
    # Force a file save path; browsers do not consistently download text/org.
    response = HttpResponse(org_bytes, content_type="application/octet-stream")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Content-Length"] = str(len(org_bytes))
    response["X-Content-Type-Options"] = "nosniff"
    return response


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
