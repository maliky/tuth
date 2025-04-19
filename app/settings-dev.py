from .settings import *

# ! Will not test real db. If I want to ttes tthe real db need to do it in docker

DATABASES["default"] = {
    "ENGINE": "django.db.backends.sqlite3",
    "NAME": ":memory:"
}

STATIC_ROOT = BASE_DIR / "../static/"
MEDIA_ROOT = BASE_DIR / "../media/"

