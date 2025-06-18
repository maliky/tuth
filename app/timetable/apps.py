"""Apps module."""

# app/timetable/apps.py
from django.apps import AppConfig


class TimetableConfig(AppConfig):
    name = "app.timetable"
    verbose_name = "Timetable"

    def ready(self):
        """Ensure timetable signals are imported when the app is ready."""
        import app.timetable.signals  # noqa: F401
