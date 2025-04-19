from .settings import *

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

