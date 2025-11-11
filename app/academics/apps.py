"""Apps module."""
# app/academics/apps.py
from django.apps import AppConfig


class AcademicsConfig(AppConfig):
    name = "app.academics"
    verbose_name = "Academics"

    def ready(self):
        """This is where one import signals."""
        pass
