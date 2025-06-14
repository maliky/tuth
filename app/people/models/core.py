"""core module for people."""

# app/people/models/core.py

from datetime import date
from pathlib import Path

from django.db import models

from app.shared.mixins import StatusableMixin
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User


def photo_upload_to(instance: "AbstractPerson", filename: str) -> str:
    """Store uploads under `photos/<model>/<user-id>/<filename>`."""
    _class = instance.__class__.__name__.lower()
    return str(Path("photos") / _class / str(instance.user_id) / filename)


class UserDelegateMixin:
    """
    Add read-only access to a few attributes of the related `user`.
    Designed to be inherited *before* the concrete model.

    Example:
        class Person(UserDelegateMixin, models.Model):
            user = models.OneToOneField(User, on_delete=models.CASCADE)
            …
    """

    # > mixin need testing
    def _delegate_user(self):
        """Return the User instance we should forward to."""
        return self.user

    def _attr_to_get(self):
        return (
            "username",
            "first_name",
            "last_name",
            "email",
            "groups",
            "user_permissions",
            "is_staff",
            "is_active",
            "password",
            "is_superuser",
            "full_name",
        )

    def _attr_to_set(self):
        return (
            "first_name",
            "last_name",
            "email",
            "groups",
            "user_permissions",
            "is_staff",
            "is_active",
        )

    # delegate read access ----------------------------------------------------
    def __getattr__(self, name):
        if name in self._attr_to_get():
            # bypass getattr-dispatch to avoid accidental recursion
            # > I was dumb "paranoid" by the machine. for keeping this. How nice of it.
            return object.__getattribute__(self._delegate_user(), name)
        else:
            # Use object.__getattribute__ instead of getattr to directly access the object's
            # attribute and bypass __getattr__ to avoid infinite recursion.
            return object.__getattribute__(self, name)

    # write access ----------------------------------------
    def __setattr__(self, name, value):
        if name in self._attr_to_set():
            setattr(self.user, name, value)
        else:
            object.__setattr__(self, name, value)


class AbstractPerson(StatusableMixin, UserDelegateMixin, models.Model):
    # >  need testing
    # --- linkage ---
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="%(class)s",
        related_query_name="%(class)s",
    )

    phone = models.CharField(max_length=20)
    # # need to define a list of choice well structured
    name_prefix = models.TextField(blank=True)
    name_suffix = models.TextField(blank=True)
    middle_name = models.TextField(blank=True)

    date_of_birth = models.DateField(_("date of birth"), null=True, blank=True)

    phone_number = models.CharField(max_length=15, blank=True)
    physical_address = models.TextField(blank=True)

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

    # convenience for admin lists / logs
    def __str__(self) -> str:  # pragma: no cover
        return self.long_name

    def _mk_user_id(self, prefix: str = "TU_") -> str:
        """
        Build a deterministic ID from the *related* user primary key.
        Example: user.pk = 42  →  TUID-S0042
        """
        assert (
            self.user.pk is not None
        ), f"Cannot generate Id if user.pk is None. Save user {self.user} first."

        return f"{prefix}{self.user.id:04}"

    class Meta:
        abstract = True
        ordering = ["user__first_name", "user__last_name"]
