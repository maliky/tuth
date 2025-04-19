from .settings_dev import *

DATABASES["default"] = {
    "ENGINE": "django.db.backends.sqlite3",
    "NAME": ":memory:"
}

STATIC_ROOT = BASE_DIR / "../static/"
MEDIA_ROOT = BASE_DIR / "../media/"

