"""Shared mixins for admin and views."""

from app.shared.utils import as_title
from django.db import models
from django.core.exceptions import ObjectDoesNotExist


class SimpleTableMixinManager(models.Manager):
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
            return super().create(code=code, label=as_title(code))


class SimpleTableMixin(models.Model):
    """Keep possible statuses for uploaded documents.

    code is a primary str key
    label is the long format for display usage.
    """

    class Meta:
        abstract = True
        ordering = ["code"]

    DEFAULT_VALUES: list[str] = []

    # ~~~~~~~~ Mandatory ~~~~~~~~
    code = models.CharField(max_length=30, primary_key=True)

    # ~~~~ Auto-filled ~~~~
    label = models.CharField(max_length=60)

    # This object manager should be temporary only to create the necessary data
    # before exporting and reimporting it.
    objects = SimpleTableMixinManager()

    @classmethod
    def _populate_attibutes_and_db(cls):
        """Create a row for each var in DEFAULT_VALUES and create subclass attributes."""
        # This method is temporary
        for val in cls.DEFAULT_VALUES:
            obj, _ = cls.objects.get_or_create(
                code=val, defaults={"label": as_title(val)}
            )
            # set variable like PENDING = 'pending', 'Pending'
            # why this ? for transition but soon obsolete
            object.__setattr__(cls, val.upper(), (val, as_title(val)))

    def __str__(self) -> str:
        """Return human readable label."""
        return self.label

    def _ensure_label(self):
        """Ensure we have a label."""
        if not self.label:
            self.label = as_title(self.code)

    def save(self, *args, **kwargs):
        """Fill empty values before save."""
        self._ensure_label()
        return super().save(*args, **kwargs)
