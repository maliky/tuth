from django.urls import path
from django.views.generic import TemplateView

urlpatterns = [
    # “admin:login” is provided by Django’s admin site
    path("", TemplateView.as_view(template_name="website/landing.html"), name="landing"),
]
