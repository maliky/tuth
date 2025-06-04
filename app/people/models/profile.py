"""Profile module."""

# app/people/models/profile.py
from __future__ import annotations

from datetime import date
from pathlib import Path

from django.contrib.auth.models import User
from django.db import models

from django.utils.translation import gettext_lazy as _

from app.shared.mixins import StatusableMixin


def photo_upload_to(instance: "BaseProfile", filename: str) -> str:
    """Store uploads under `photos/<model>/<user-id>/<filename>`."""
    _class = instance.__class__.__name__.lower()
    return str(Path("photos") / _class / str(instance.user_id) / filename)


class BaseProfile(StatusableMixin, models.Model):
    """Common demographic & contact information for every person on campus."""

    # --- linkage ---
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="%(class)s",
        related_query_name="%(class)s",
    )
    # User model will provide : username, first_name, last_name, email, groups, user_permissions, is_staff, is_active, password, is_superuser, last_login,  date_joined, full_name

    # --- titles ---
    # # need to define a list of choice well structured
    name_prefix = models.TextField(blank=True)
    name_suffix = models.TextField(blank=True)
    middle_name = models.TextField(blank=True)

    # --- demographics ---
    date_of_birth = models.DateField(_("date of birth"), null=True, blank=True)
    # --- contact ---
    phone_number = models.CharField(max_length=15, blank=True)
    physical_address = models.TextField(blank=True)

    # --- misc ---
    bio = models.TextField(blank=True)
    photo = models.ImageField(upload_to=photo_upload_to, null=True, blank=True)

    @property
    def full_name(self) -> str:
        fullname = " ".join(
            [
                self.name_prefix,
                self.user.first_name,
                self.middle_name,
                self.user.last_name,
                self.name_suffix,
            ]
        ).strip()
        return fullname

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
        return self.full_name

    class Meta:
        abstract = True
        ordering = ["user__last_name", "user__first_name"]


class StudentProfile(BaseProfile):
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

    # convenience computed property
    class Meta(BaseProfile.Meta):
        verbose_name = _("student profile")
        verbose_name_plural = _("student profiles")


class StaffProfile(BaseProfile):
    """Generic data for all employees of the university."""

    staff_id = models.CharField(max_length=20, unique=True)
    employment_date = models.DateField(null=True, blank=True)

    division = models.CharField(max_length=100, blank=True)
    department = models.CharField(max_length=100, blank=True)
    position = models.CharField(max_length=50, blank=True)

    class Meta(BaseProfile.Meta):
        verbose_name = _("staff profile")
        verbose_name_plural = _("staff profiles")


class FacultyProfile(StaffProfile):
    """Faculty member who teaches courses."""

    college = models.ForeignKey(
        "academics.College", on_delete=models.SET_NULL, null=True, blank=True
    )
    google_profile = models.URLField(blank=True)
    personal_website = models.URLField(blank=True)

    class Meta(StaffProfile.Meta):
        verbose_name = _("faculty profile")
        verbose_name_plural = _("faculty profiles")


class DonorProfile(BaseProfile):
    """Contact information for donors supporting students."""

    donor_id = models.CharField(max_length=20, unique=True)
    contact_via_email = models.BooleanField(default=True)
    contact_via_phone = models.BooleanField(default=False)

    class Meta(BaseProfile.Meta):
        verbose_name = _("donor profile")
        verbose_name_plural = _("donor profiles")
