"""Modularized views exposed under the legacy import path."""

from .auth import PortalLoginView, PortalLogoutView, portal_redirect
from .enrollment import (
    create_student,
    student_admin_edit,
    student_autocomplete,
    student_delete,
    student_detail,
    student_list,
)
from .finance_officer import (
    finance_officer_create_payments,
    finance_officer_invoices,
    finance_officer_student_autocomplete,
    finance_officer_update_payments,
)
from .registrar import registrar_course_windows
from .staff_dashboards import staff_dashboard, staff_role_dashboard
from .student_dashboard import (
    download_invoice_statement,
    student_dashboard,
    student_invoice_statement,
)

__all__ = [
    "PortalLoginView",
    "PortalLogoutView",
    "create_student",
    "portal_redirect",
    "registrar_course_windows",
    "staff_dashboard",
    "staff_role_dashboard",
    "student_dashboard",
    "student_admin_edit",
    "student_autocomplete",
    "student_delete",
    "student_detail",
    "student_list",
    "student_invoice_statement",
    "download_invoice_statement",
    "finance_officer_invoices",
    "finance_officer_create_payments",
    "finance_officer_student_autocomplete",
    "finance_officer_update_payments",
]
