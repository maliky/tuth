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
        views.student_invoice_statement,
        name="student_invoice_statement",
    ),
    path(
        "student/invoice/statement/download/",
        views.download_invoice_statement,
        name="student_invoice_statement_download",
    ),
    path(
        "student/payment/receipt/<int:semester_id>/",
        views.student_payment_receipt,
        name="student_payment_receipt",
    ),
    path(
        "student/sections/<int:section_id>/",
        views.student_section_detail,
        name="student_section_detail",
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
        views.finance_officer_student_autocomplete,
        name="finance_officer_student_autocomplete",
    ),
    # Course dashboard removed in favor of the student dashboard flow.
    path("students/", views.student_list, name="student_list"),
    path("students/<int:pk>", views.student_detail, name="student_detail"),
    path("students/<int:pk>/delete/", views.student_delete, name="student_delete"),
    path("students/new/", views.create_student, name="create_student"),
    path(
        "students/autocomplete/",
        views.student_autocomplete,
        name="student_autocomplete",
    ),
    path(
        "students/admin-edit/",
        views.student_admin_edit,
        name="student_admin_edit",
    ),
    path(
        "registrar/course-windows/",
        views.registrar_course_windows,
        name="registrar_course_windows",
    ),
]
