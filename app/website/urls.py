"""Urls module."""

from django.urls import path
from django.views.generic import TemplateView

from . import views


urlpatterns = [
    # “admin:login” is provided by Django’s admin site
    path("", TemplateView.as_view(template_name="website/landing.html"), name="landing"),
    path("registration/", views.registration_dashboard, name="registration_dashboard"),
    path("students/new/", views.create_student, name="create_student"),
]
