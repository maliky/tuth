"""core module for people."""

# app/people/models/core.py

from datetime import date
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from app.shared.mixins import StatusableMixin

User = get_user_model()


def photo_upload_to(instance: "AbstractPerson", filename: str) -> str:
    """Store uploads under `photos/<model>/<user-id>/<filename>`."""
    _class = instance.__class__.__name__.lower()
    return str(Path("photos") / _class / str(instance.user_id) / filename)


class AbstractPerson(StatusableMixin, models.Model):

    ID_FIELD: str | None = None
    ID_PREFIX: str = "TU_"

    # >  need testing
    # --- linkage ---
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="%(class)s",
        related_query_name="%(class)s",
    )

    # # need to define a list of choice well structured
    name_prefix = models.CharField(blank=True)
    name_suffix = models.CharField(blank=True)
    middle_name = models.CharField(blank=True)

    date_of_birth = models.DateField(_("date of birth"), null=True, blank=True)

    phone_number = models.CharField(max_length=15, blank=True)
    physical_address = models.CharField(blank=True)

    # --- misc ---
    bio = models.TextField(blank=True)
    photo = models.ImageField(upload_to=photo_upload_to, null=True, blank=True)

    @property
    def long_name(self) -> str:
        long_name = " ".join(
            [
                self.name_prefix,
                self.first_name,
                self.middle_name,
                self.last_name,
                self.name_suffix,
            ]
        ).strip()
        return long_name

    @property
    def age(self) -> int | None:
        if self.date_of_birth:
            today = date.today()
            return (
                today.year
                - self.date_of_birth.year
                # moins 1 ou 0, si l'anniversaire est passé cette année.
                - (
                    (today.month, today.day)
                    < (self.date_of_birth.month, self.date_of_birth.day)
                )
            )
        return None
    @property
    def username(self):
        return self.user.username

    @property
    def first_name(self):
        return self.user.first_name

    @property
    def last_name(self):
        return self.user.last_name

    @property
    def full_name(self):
        return self.user.full_name

    @property
    def email(self):
        return self.user.email

    def set_username(self, value):
        return object._setattr__(self.user, "username", value)

    def set_first_name(self, value):
        return object._setattr__(self.user, "first_name", value)

    def set_last_name(self, value):
        return object._setattr__(self.user, "last_name", value)

    def set_full_name(self, value):
        return object._setattr__(self.user, "full_name", value)

    def set_email(self, value):
        return object._setattr__(self.user, "email", value)


    # convenience for admin lists / logs
    def __str__(self) -> str:  # pragma: no cover
        return self.long_name

    def _exists_user(self):
        try:
            _ = self.user
        except User.DoesNotExist:
            raise ValidationError("User must have been saved at this point.")

    def _mk_id(self) -> str:
        """
        Build a deterministic ID from the *related* user primary key.
        Example: user.pk = 42  →  TUID-S0042
        """
        self._exists_user()
        assert self.user.pk is not None, "Cannot generate Id if user.pk is None."

        return f"{self.ID_PREFIX}{self.user.id:04}"

    def save(self, *args, **kwargs):
        """the attribute is for eg donor_id or staff_id and the prefix is used in the _mk_id"""
        super().save(*args, **kwargs)
        id_field = self.ID_FIELD
        assert id_field, "needs to be set / override, is the field to set"
        new_id = self._mk_id()
        object.__setattr__(self, id_field, new_id)
        super().save(update_fields=[id_field])

    class Meta:
        abstract = True
        ordering = ["user__first_name", "user__last_name"]
