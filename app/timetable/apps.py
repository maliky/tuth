"""Apps module."""

# app/timetable/apps.py
from django.apps import AppConfig


class TimetableConfig(AppConfig):
    name = "app.timetable"
    verbose_name = "Timetable"

    def ready(self):
        """This is where one import signals."""
        pass
