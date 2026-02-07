"""Invoice snapshot printing views."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from app.finance.models.invoice import Invoice
from app.finance.utils import build_invoice_snapshot, render_invoice_snapshot_pdf
from app.timetable.models.semester import Semester

from .student_helpers import _require_student


@login_required
def student_invoice_snapshot_pdf(request: HttpRequest) -> HttpResponse:
    """Generate and download a PDF invoice snapshot for the student."""
    student = _require_student(request.user)
    semester_id = request.GET.get("semester")
    semester = None
    invoice_qs = (
        Invoice.objects.filter(student=student, balance__gt=0)
        .select_related(
            "curriculum_course__course",
            "curriculum_course__credit_hours",
            "semester",
            "semester__academic_year",
        )
        .prefetch_related(
            "curriculum_course__course__course_fee_stacks__effective_from_semester",
            "curriculum_course__course__course_fee_stacks__effective_to_semester",
            "curriculum_course__course__course_fee_stacks__fee_stack__fees__fee_type",
        )
    )
    if semester_id:
        semester = get_object_or_404(Semester, pk=semester_id)
        invoice_qs = invoice_qs.filter(semester=semester)

    snapshot = build_invoice_snapshot(
        invoice_qs,
        student=student,
        semester=semester,
        created_by=None,
    )
    pdf_bytes = render_invoice_snapshot_pdf(snapshot)
    timestamp = timezone.now().strftime("%Y%m%d_%H%M")
    filename = f"invoice_{student.student_id}_{timestamp}.pdf"
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
