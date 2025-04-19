from dotenv import load_dotenv
import os
from .settings import *

load_dotenv(BASE_DIR / ".env-prod") # not necessary in the docker see env loaded with env_file
DEBUG = False

# python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS").split()
CSRF_TRUSTED_ORIGINS = os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS").split()

DATABASES = {
    #https://docs.djangoproject.com/en/5.2/ref/databases/#postgresql-notes
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB"),
        "USER": os.getenv("POSTGRES_USER"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD"),
        "HOST": os.getenv("POSTGRES_HOST"),  # db is the docker-compose service
        "PORT": os.getenv("POSTGRES_PORT")
    }
}

