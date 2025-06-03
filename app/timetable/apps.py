"""Apps module."""

# app/timetable/apps.py
from django.apps import AppConfig


class TimetableConfig(AppConfig):
    name = "app.timetable"
    verbose_name = "Timetable"

    def ready(self):
        """
        this garanties that my signal are imported when I use the application.
        """
        import app.timetable.signals  # noqa: F401
