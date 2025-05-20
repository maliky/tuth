from django.apps import AppConfig  # , apps


class TuthAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app"

    def ready(self):
        """
        this garanties that my signal are imported when I use the application.
        """
        import app.models  # noqa: F401

        # import app.models.signals  # noqa: F401
        #        apps.get_models()
