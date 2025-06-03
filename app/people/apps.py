"""Apps module."""

# app/people/apps.py
from django.apps import AppConfig


class PeopleConfig(AppConfig):
    name = "app.people"
    verbose_name = "People"
