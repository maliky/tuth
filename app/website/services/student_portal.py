"""Compatibility façade for student portal services."""

from __future__ import annotations

from app.website.services.student_dashboard_service import student_dashboard_response
from app.website.services.student_finance import (
    download_invoice_statement_response,
    std_invoice_statement_response,
)

__all__ = [
    "download_invoice_statement_response",
    "std_invoice_statement_response",
    "student_dashboard_response",
]
