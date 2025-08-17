"""Shared mixins for admin and views."""

from django.db import models
from django.core.exceptions import ObjectDoesNotExist


class StatusManager(models.Manager):
    """Automatically create status on demand."""

    def get(self, *args, **kwargs):  # type: ignore[override]
        """Return existing credit hour or create it if missing."""
        try:
            return super().get(*args, **kwargs)
        except ObjectDoesNotExist:
            code = kwargs.get("code")
            if code is None:
                raise
            # Use the numeric code as the human-readable label
            return super().create(code=code, label=str(code))


class StatusMixin(models.Model):
    """Keep possible statuses for uploaded documents."""

    class Meta:
        abstract = True
        ordering = ["code"]

    code = models.CharField(max_length=30, primary_key=True)
    label = models.CharField(max_length=60)

    objects = StatusManager()

    def __str__(self) -> str:
        """Return human readable label."""
        return self.label
