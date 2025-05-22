from __future__ import annotations

from django.db import models


class Profile(models.Model):
    user = models.OneToOneField("auth.User", on_delete=models.CASCADE)
