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
    path("courses/", views.course_dashboard, name="course_dashboard"),
    path("students/", views.student_list, name="student_list"),
    path("students/<int:pk>", views.student_detail, name="student_detail"),
    path("students/<int:pk>/delete/", views.student_delete, name="student_delete"),
    path("students/new/", views.create_student, name="create_student"),
    path(
        "registrar/course-windows/",
        views.registrar_course_windows,
        name="registrar_course_windows",
    ),
]
