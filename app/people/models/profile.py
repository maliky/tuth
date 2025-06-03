# app/people/models/profile.py
from __future__ import annotations

from datetime import date
from pathlib import Path
from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import gettext_lazy as _

from app.shared.mixins import StatusableMixin
from app.shared.constants import TEST_PW


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def photo_upload_to(instance: "BaseProfile", filename: str) -> str:
    """Store uploads under `photos/<model>/<user-id>/<filename>`."""
    _class = instance.__class__.__name__.lower()
    return str(Path("photos") / _class / str(instance.user_id) / filename)


# ──────────────────────────────────────────────────────────────────────────────
# Abstract base with all shared columns  ( **NO TABLE CREATED** )
# ──────────────────────────────────────────────────────────────────────────────
class BaseProfile(StatusableMixin, models.Model):
    """Common demographic & contact information for every person on campus."""

    # --- linkage ---
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="%(class)s",
        related_query_name="%(class)s",
    )

    # --- demographics ---
    date_of_birth = models.DateField(_("date of birth"), null=True, blank=True)

    # --- contact ---
    phone_number = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    personal_email = models.EmailField(_("personal e-mail"), blank=True)

    # --- misc ---
    bio = models.TextField(blank=True)
    photo = models.ImageField(upload_to=photo_upload_to, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def age(self) -> int | None:
        if self.date_of_birth:
            today = date.today()
            return (
                today.year
                - self.date_of_birth.year
                - (
                    (today.month, today.day)
                    < (self.date_of_birth.month, self.date_of_birth.day)
                )
            )
        return None

    # convenience for admin lists / logs
    def __str__(self) -> str:  # pragma: no cover
        return self.user.get_full_name() or self.user.username

    class Meta:
        abstract = True
        ordering = ["user__first_name", "user__last_name"]


# ──────────────────────────────────────────────────────────────────────────────
# Student
# ──────────────────────────────────────────────────────────────────────────────
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

    # convenience computed property
    class Meta(BaseProfile.Meta):
        verbose_name = _("student profile")
        verbose_name_plural = _("student profiles")


# ──────────────────────────────────────────────────────────────────────────────
# Staff (non-teaching personnel)
# ──────────────────────────────────────────────────────────────────────────────
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


# ──────────────────────────────────────────────────────────────────────────────
# Faculty / Instructor ( specialised Staff )
# ──────────────────────────────────────────────────────────────────────────────
class FacultyProfile(StaffProfile):
    """Faculty member who teaches courses."""

    college = models.ForeignKey(
        "academics.College", on_delete=models.SET_NULL, null=True, blank=True
    )
    courses = models.ManyToManyField(
        "academics.Course", related_name="facultys", blank=True
    )

    google_profile = models.URLField(blank=True)
    personal_website = models.URLField(blank=True)

    class Meta(StaffProfile.Meta):
        verbose_name = _("faculty profile")
        verbose_name_plural = _("faculty profiles")


# ──────────────────────────────────────────────────────────────────────────────
# Donor
# ──────────────────────────────────────────────────────────────────────────────
class DonorProfile(BaseProfile):
    """Contact information for donors supporting students."""

    donor_id = models.CharField(max_length=20, unique=True)
    contact_via_email = models.BooleanField(default=True)
    contact_via_phone = models.BooleanField(default=False)

    class Meta(BaseProfile.Meta):
        verbose_name = _("donor profile")
        verbose_name_plural = _("donor profiles")


def _ensure_faculty(fullname: str, college: "College") -> FacultyProfile:
    """Return a :class:`FacultyProfile` for *fullname*, creating records.

    Splits the provided ``fullname`` into first and last names, constructs a
    username from the initials of the given names and the last name, and then
    ensures both the ``User`` and associated ``FacultyProfile`` exist.  The user
    password is set to ``TEST_PW`` when created.
    """

    parts = fullname.split()
    if not parts:
        raise ValueError("fullname cannot be empty")

    first = parts[0]
    last = parts[-1]
    initials = "".join(p[0] for p in parts[:-1]) or first[0]
    username = f"{initials}.{last}".lower()

    user, created = User.objects.get_or_create(
        username=username,
        defaults={"first_name": first, "last_name": last, "password": TEST_PW},
    )
    if created:
        user.set_password(TEST_PW)
        user.save()

    profile, _ = FacultyProfile.objects.get_or_create(
        user=user, defaults={"college": college}
    )
    return profile
