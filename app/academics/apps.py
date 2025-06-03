"""Apps module."""

# app/academics/apps.py
from django.apps import AppConfig


class AcademicsConfig(AppConfig):
    name = "app.academics"
    verbose_name = "Academics"

    def ready(self):
        """
        this garanties that my signal are imported when I use the application.
        """
        import app.academics.signals  # noqa: F401
