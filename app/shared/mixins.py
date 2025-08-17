"""Shared mixins for admin and views."""

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
            return super().create(code=code, label=code.replace("_", " ").title())


class SimpleTableMixin(models.Model):
    """Keep possible statuses for uploaded documents."""

    class Meta:
        abstract = True
        ordering = ["code"]

    TABLE_DEFAULT_VALUES: list[str] = []
    code = models.CharField(max_length=30, primary_key=True)
    label = models.CharField(max_length=60)

    objects = SimpleTableMixinManager()

    # not sure about class method in abstract classes
    # @classmethod
    # def _populate_attibutes_and_db(cls):
    #     """Create a row for each var in TABLE_DEFAULT_VALUES and populate the core attributes."""
    #     # Would be good to have a list of variables (v)
    #     # and for each create / populate the table code/label (v.title())
    #     # and set them are class attributes

    #     for val in cls.TABLE_DEFAULT_VALUES:
    #         obj, _ = cls.objects.get_or_create(code=val, label=cls.clean(val))
    #         # set variable like PENDING = 'pending', 'Pending'
    #         object.__setattr__(cls, val.upper(), (val, cls._clean(val)))

    def _clean(self, value):
        return value.replace("_", " ").title()

    def __str__(self) -> str:
        """Return human readable label."""
        return self.label
