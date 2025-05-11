from django.apps import AppConfig


class TuthAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app"

    def ready(self):
        """
        this garanties that my signal are imported when I use the application.
        """
        import app.models  # noqa: F401
