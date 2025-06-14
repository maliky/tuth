"""Profiles module."""

# app/people/models/profiles.py

from __future__ import annotations

from datetime import date
from pathlib import Path

from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.db import models
from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _

from app.academics.models.curriculum import Curriculum
from app.shared.mixins import StatusableMixin

if TYPE_CHECKING:  # pragma: no cover - hints only
    from app.academics.models import College


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

    class Meta:
        abstract = True
        ordering = ["user__first_name", "user__last_name"]


class Staff(AbstractPerson):
    """Base class for Staffs."""

    # should be created on the fly and be unique (use some cultural combination of words)
    staff_id = models.CharField(max_length=13, unique=True)
    employment_date = models.DateField(null=True, blank=True)

    division = models.CharField(max_length=100, blank=True)
    # ! if talking of faculty they could be in different departments
    # ! would need a foreign key here
    department = models.CharField(max_length=100, blank=True)
    position = models.CharField(max_length=50, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user"], name="uniq_staff_per_user")
        ]


class Donor(AbstractPerson, models.Model):
    """Contact information for donors supporting students."""

    donor_id = models.CharField(max_length=20, unique=True)


class Faculty(StatusableMixin, UserDelegateMixin, models.Model):
    staff_profile = models.OneToOneField(Staff, on_delete=models.CASCADE)
    college = models.ForeignKey(
        "academics.College", on_delete=models.SET_NULL, null=True, blank=True
    )
    google_profile = models.URLField(blank=True)
    personal_website = models.URLField(blank=True)
    academic_rank = models.CharField(max_length=50, null=True, blank=True)
    # teaching load should be a function per semester or year
    # teaching_load = models.IntegerField()

    @property
    def curricula(self) -> QuerySet[Curriculum]:
        """
        Return all Curriculum instances in which this faculty is teaching.

        Traverses: Curriculum → courses → sections → session → faculty
        """
        return Curriculum.objects.filter(
            courses__sections__session__faculty=self
        ).distinct()

    #

    def _delegate_user(self):
        """Return the User instance we should forward to."""
        return self.staff_profile.user


class Student(AbstractPerson):
    """Extra academic information for enrolled students."""

    student_id = models.CharField(max_length=20, unique=True)

    # academics
    college = models.ForeignKey(
        "academics.College", on_delete=models.SET_NULL, null=True, blank=True
    )
    curriculum = models.ForeignKey(
        "academics.Curriculum", on_delete=models.SET_NULL, null=True, blank=True
    )

    # > This should an semester. Can be any of 1 or 2
    # > update this field with FK
    enrollment_semester = models.PositiveSmallIntegerField()
    enrollment_date = models.DateField(null=True, blank=True)

    # > need to create a method to compute le level of the student based on the number
    # of credit completed
    # def credit_completed(self) -> int:
    #     self.courses.credit


def _ensure_faculty(full_name: str, college: "College") -> Faculty:
    """Return a :class:`Faculty` for ``full_name`` in ``college``.

    Creates the related ``User`` and ``Staff`` rows when necessary.  Accounts
    are generated using a ``j.doe`` style username and the default test
    password.
    """

    from app.shared.constants import TEST_PW

    parts = full_name.split()
    first = parts[0] if parts else ""
    last = parts[-1] if len(parts) > 1 else ""

    base = f"{first[:1].lower()}.{last.lower()}"
    username = base or "user"
    counter = 1
    User = get_user_model()
    while True:
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"first_name": first, "last_name": last},
        )
        if created:
            user.set_password(TEST_PW)
            user.save()
            break
        if user.first_name == first and user.last_name == last:
            break
        counter += 1
        username = f"{base}{counter}"

    staff_id = f"TU-{username}"
    staff, _ = Staff.objects.get_or_create(
        user=user,
        defaults={"staff_id": staff_id, "phone": "000"},
    )

    fac, _ = Faculty.objects.get_or_create(
        staff_profile=staff,
        defaults={"college": college},
    )
    return fac
