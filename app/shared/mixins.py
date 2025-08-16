"""Shared mixins for admin and views."""

from django.db import models


class StatusMixin(models.Model):
    """Keep possible statuses for uploaded documents."""

    class Meta:
        abstract = True
        ordering = ["code"]

    code = models.CharField(max_length=30, primary_key=True)
    label = models.CharField(max_length=60)

    def __str__(self) -> str:
        """Return human readable label."""
        return self.label
