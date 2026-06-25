"""Modularized views exposed under the legacy import path."""

from .account import account_profile
from .auth import PortalLoginView, PortalLogoutView, portal_redirect
from .dean import (
    dean_curricula,
    dean_curriculum_detail,
    dean_curriculum_request_activation,
)
from .enrollment import (
    create_std,
    curriculum_autocomplete,
    std_admin_edit,
    std_autocomplete,
    std_delete,
    std_detail,
    std_list,
)
from .finance_officer import (
    finance_officer_create_payments,
    finance_officer_generate_registration_invoices,
    finance_officer_invoices,
    finance_officer_setup_registration_fee,
    finance_officer_std_autocomplete,
    finance_officer_update_payments,
)
from .faculty import (
    faculty_grade_roster,
    faculty_grade_roster_autosave,
    faculty_grade_roster_download,
    faculty_grade_roster_upload,
    faculty_grade_sections,
)
from .grade_roster_oversight import (
    staff_grade_roster_detail,
    staff_grade_rosters,
)
from .registrar import (
    reg_class_roster_detail,
    reg_class_rosters,
    reg_crs_wins,
    reg_faculty_autocomplete,
    reg_grades_dashboard,
    reg_grade_semester_editor,
    reg_grade_transcript,
    reg_grade_transcript_org,
    reg_grade_transcript_pdf,
    reg_grade_transcripts_bulk_pdf,
    reg_std_autocomplete,
)
from .staff_dashboards import staff_dashboard, staff_role_dashboard
from .transcripts import transcript_verify, transcript_verify_pdf
from .vpaa import (
    vpaa_approval_approve,
    vpaa_approval_detail,
    vpaa_approval_mark_review,
    vpaa_approval_reject,
    vpaa_approvals,
)
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
    "account_profile",
    "create_std",
    "curriculum_autocomplete",
    "dean_curricula",
    "dean_curriculum_detail",
    "dean_curriculum_request_activation",
    "portal_redirect",
    "reg_class_roster_detail",
    "reg_class_rosters",
    "reg_crs_wins",
    "reg_faculty_autocomplete",
    "reg_grades_dashboard",
    "reg_grade_semester_editor",
    "reg_grade_transcript",
    "reg_grade_transcript_org",
    "reg_grade_transcript_pdf",
    "reg_grade_transcripts_bulk_pdf",
    "reg_std_autocomplete",
    "staff_dashboard",
    "staff_grade_roster_detail",
    "staff_grade_rosters",
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
    "transcript_verify",
    "transcript_verify_pdf",
    "finance_officer_invoices",
    "finance_officer_create_payments",
    "finance_officer_generate_registration_invoices",
    "finance_officer_std_autocomplete",
    "finance_officer_setup_registration_fee",
    "finance_officer_update_payments",
    "faculty_grade_roster",
    "faculty_grade_roster_autosave",
    "faculty_grade_roster_download",
    "faculty_grade_roster_upload",
    "faculty_grade_sections",
    "vpaa_approval_approve",
    "vpaa_approval_detail",
    "vpaa_approval_mark_review",
    "vpaa_approval_reject",
    "vpaa_approvals",
]
