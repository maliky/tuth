"""Student dashboard view wrappers."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_POST

from app.website.services.student_portal import (
    download_invoice_statement_response,
    std_invoice_statement_response,
    student_dashboard_response,
)


@login_required
@require_POST
def download_invoice_statement(request: HttpRequest) -> HttpResponse:
    """Redirect to the invoice statement view."""
    return download_invoice_statement_response(request)


@login_required
def std_invoice_statement(request: HttpRequest) -> HttpResponse:
    """Render the invoice statement for the current student."""
    return std_invoice_statement_response(request)


@login_required
def student_dashboard(request: HttpRequest) -> HttpResponse:
    """Render the student dashboard backed with live data."""
    return student_dashboard_response(request)
