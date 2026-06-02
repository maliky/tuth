"""Modularized views exposed under the legacy import path."""

from .auth import PortalLoginView, PortalLogoutView, portal_redirect
from .dean import (
    dean_curricula,
    dean_curriculum_detail,
    dean_curriculum_request_activation,
)
from .enrollment import (
    create_std,
    std_admin_edit,
    std_autocomplete,
    std_delete,
    std_detail,
    std_list,
)
from .finance_officer import (
    finance_officer_create_payments,
    finance_officer_invoices,
    finance_officer_std_autocomplete,
    finance_officer_update_payments,
)
from .registrar import (
    reg_crs_wins,
    reg_grades_dashboard,
    reg_grade_transcript,
    reg_std_autocomplete,
)
from .staff_dashboards import staff_dashboard, staff_role_dashboard
from .student_dashboard import (
    download_invoice_statement,
    student_dashboard,
    std_invoice_statement,
)
from .student_curriculum import (
    std_curri_crs_detail,
    std_curri_crss,
)
from .invoice_snapshots import std_invoice_snapshot_pdf
from .student_payment_receipts import std_payment_receipt
from .student_sections import std_sec_detail

__all__ = [
    "PortalLoginView",
    "PortalLogoutView",
    "create_std",
    "dean_curricula",
    "dean_curriculum_detail",
    "dean_curriculum_request_activation",
    "portal_redirect",
    "reg_crs_wins",
    "reg_grades_dashboard",
    "reg_grade_transcript",
    "reg_std_autocomplete",
    "staff_dashboard",
    "staff_role_dashboard",
    "student_dashboard",
    "std_admin_edit",
    "std_autocomplete",
    "std_delete",
    "std_detail",
    "std_list",
    "std_invoice_statement",
    "download_invoice_statement",
    "std_curri_crss",
    "std_curri_crs_detail",
    "std_payment_receipt",
    "std_sec_detail",
    "std_invoice_snapshot_pdf",
    "finance_officer_invoices",
    "finance_officer_create_payments",
    "finance_officer_std_autocomplete",
    "finance_officer_update_payments",
]
