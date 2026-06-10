"""Urls module."""

from django.urls import path
from django.views.generic import TemplateView

from . import views


urlpatterns = [
    # “admin:login” is provided by Django’s admin site
    path("", TemplateView.as_view(template_name="website/landing.html"), name="landing"),
    path("student/dashboard/", views.student_dashboard, name="student_dashboard"),
    path("staff/dashboard/", views.staff_dashboard, name="staff_dashboard"),
    path("staff/<slug:role>/", views.staff_role_dashboard, name="staff_role_dashboard"),
    path("portal/", views.portal_redirect, name="portal_redirect"),
    path("auth/login/", views.PortalLoginView.as_view(), name="portal_login"),
    path("auth/logout/", views.PortalLogoutView.as_view(), name="portal_logout"),
    path(
        "student/invoice/statement/",
        views.std_invoice_statement,
        name="std_invoice_statement",
    ),
    path(
        "student/invoice/statement/download/",
        views.download_invoice_statement,
        name="student_invoice_statement_download",
    ),
    path(
        "student/invoice/statement/print/",
        views.std_invoice_snapshot_pdf,
        name="std_invoice_snapshot_pdf",
    ),
    path(
        "student/payment/receipt/<int:semester_id>/",
        views.std_payment_receipt,
        name="std_payment_receipt",
    ),
    path(
        "student/sections/<int:section_id>/",
        views.std_sec_detail,
        name="std_sec_detail",
    ),
    path(
        "student/curriculum/",
        views.std_curri_crss,
        name="std_curri_crss",
    ),
    path(
        "student/curriculum/<int:curriculum_course_id>/",
        views.std_curri_crs_detail,
        name="std_curri_crs_detail",
    ),
    path(
        "staff/dean/curricula/",
        views.dean_curricula,
        name="dean_curricula",
    ),
    path(
        "staff/dean/curricula/<int:curriculum_id>/",
        views.dean_curriculum_detail,
        name="dean_curriculum_detail",
    ),
    path(
        "staff/dean/curricula/<int:curriculum_id>/request-activation/",
        views.dean_curriculum_request_activation,
        name="dean_curriculum_request_activation",
    ),
    path(
        "staff/vpaa/approvals/",
        views.vpaa_approvals,
        name="vpaa_approvals",
    ),
    path(
        "staff/vpaa/approvals/<int:approval_id>/",
        views.vpaa_approval_detail,
        name="vpaa_approval_detail",
    ),
    path(
        "staff/vpaa/approvals/<int:approval_id>/review/",
        views.vpaa_approval_mark_review,
        name="vpaa_approval_mark_review",
    ),
    path(
        "staff/vpaa/approvals/<int:approval_id>/approve/",
        views.vpaa_approval_approve,
        name="vpaa_approval_approve",
    ),
    path(
        "staff/vpaa/approvals/<int:approval_id>/reject/",
        views.vpaa_approval_reject,
        name="vpaa_approval_reject",
    ),
    path(
        "staff/finance/invoices/",
        views.finance_officer_invoices,
        name="finance_officer_invoices",
    ),
    path(
        "staff/finance/invoices/create-payments/",
        views.finance_officer_create_payments,
        name="finance_officer_create_payments",
    ),
    path(
        "staff/finance/invoices/update-payments/",
        views.finance_officer_update_payments,
        name="finance_officer_update_payments",
    ),
    path(
        "staff/finance/students/autocomplete/",
        views.finance_officer_std_autocomplete,
        name="finance_officer_std_autocomplete",
    ),
    # Course dashboard removed in favor of the student dashboard flow.
    path("students/", views.std_list, name="std_list"),
    path("students/<int:pk>", views.std_detail, name="std_detail"),
    path("students/<int:pk>/delete/", views.std_delete, name="std_delete"),
    path("students/new/", views.create_std, name="create_std"),
    path(
        "students/autocomplete/",
        views.std_autocomplete,
        name="std_autocomplete",
    ),
    path(
        "students/admin-edit/",
        views.std_admin_edit,
        name="std_admin_edit",
    ),
    path(
        "registrar/course-windows/",
        views.reg_crs_wins,
        name="reg_crs_wins",
    ),
    path(
        "registrar/grades/",
        views.reg_grades_dashboard,
        name="reg_grades_dashboard",
    ),
    path(
        "registrar/grades/<int:student_id>/transcript/",
        views.reg_grade_transcript,
        name="reg_grade_transcript",
    ),
    path(
        "registrar/grades/students/autocomplete/",
        views.reg_std_autocomplete,
        name="reg_std_autocomplete",
    ),
]
