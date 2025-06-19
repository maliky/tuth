"""Core module for people."""

# app/people/models/core.py

from datetime import date
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from app.shared.status.mixins import StatusableMixin

User = get_user_model()


def photo_upload_to(instance: "AbstractPerson", filename: str) -> str:
    """Store uploads under `photos/<model>/<user-id>/<filename>`."""
    _class = instance.__class__.__name__.lower()
    return str(Path("photos") / _class / str(instance.user_id) / filename)


class AbstractPerson(StatusableMixin, models.Model):
    """Base information shared by all people profiles.

    Example:
        >>> from django.contrib.auth import get_user_model
        >>> User = get_user_model()
        >>> user = User.objects.create(username="john")
        >>> from app.people.models.student import Student
        >>> Student.objects.create(user=user, student_id="S1", enrollment_semester=semester)

    Side Effects:
        ``save()`` assigns an ID derived from ``user``.
    """

    ID_FIELD: str | None = None
    ID_PREFIX: str = "TU-"

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
        """Get the long name from the different name parts."""
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
        """Compute and returns the age of the abstract user."""
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
        """Returns the username."""
        return self.user.username

    @property
    def first_name(self):
        """Returns the first_name."""
        return self.user.first_name

    @property
    def last_name(self):
        """Returns the last_name."""
        return self.user.last_name

    @property
    def full_name(self):
        """Returns the full name, that is first and last names."""
        return self.user.get_full_name()

    @property
    def email(self):
        """Return the use email."""
        return self.user.email

    def set_username(self, value):
        """Set the username."""
        return object.__setattr__(self.user, "username", value)

    def set_first_name(self, value):
        """Sets the firstname."""
        return object.__setattr__(self.user, "first_name", value)

    def set_last_name(self, value):
        """Sets the lastname."""
        return object.__setattr__(self.user, "last_name", value)

    def set_email(self, value):
        """Sets the email."""
        return object.__setattr__(self.user, "email", value)

    # convenience for admin lists / logs
    def __str__(self) -> str:  # pragma: no cover
        return self.long_name

    def _exists_user(self) -> None:
        """Returns the user if it exists."""
        try:
            _ = self.user
        except User.DoesNotExist:
            raise ValidationError("User must have been saved at this point.")

    def _mk_id(self) -> str:
        """Build a deterministic ID from the *related* user primary key.

        Example: user.pk = 42  →  TUID-S0042
        """
        # > we need a better logic tolarating existing id.
        # > the Id number should not be linked to the user but the the students
        # > the logic should go do.
        # > If I create a student a donor a staff a staff a student I should seed
        # > tu00001, dnr00001, stf00001, stf00002, tu00002.
        self._exists_user()

        if self.user.pk is None:
            raise ValidationError("Cannot generate Id if user.pk is None.")

        # > I want to get all the ids of the class of objet calling this function (Staff, Donor, Student...)
        # > Then I order those number (they will have been strip of the ID_PREFIX)
        # > I identify gaps in the number sequence.  (non attributed no)
        # > I create a new number withing that gap.
        # > Could be speeded up if I kept in a table for each class the available numbers below the highest
        # > attributed to that class.
        # > if no number available the I would just give the next integer.
        return f"{self.ID_PREFIX}{self.user.id:05}"

    def id_field_exists(self) -> None:
        """Raise an exception if ID_PREFIX is not set."""
        # > the check will not be detected by mypy. so ignore[arg-type]
        # would be good to find more clean to use mypy
        if not self.ID_FIELD:
            raise ValidationError("ID_FIELD needs to be set before creating new ID.")

    def get_id_no(self) -> int | None:
        """Remove the ID_PREFIX and Returns the number associated with the id field."""
        self.id_field_exists()
        obj_id = object.__getattribute__(self, self.ID_FIELD)  # type: ignore[arg-type]

        if obj_id is None:
            return None

        _, _, obj_no_str = obj_id.partition(self.ID_PREFIX)  # type: ignore[arg-type]
        return int(obj_no_str)

    def save(self, *args, **kwargs):
        """Create an ID and saves it for each model using _mk_id and ID_FIELD."""
        id_no = self.get_id_no()
        if id_no is None:
            new_id = self._mk_id()
            object.__setattr__(self, self.ID_FIELD, new_id)  # type: ignore[arg-type]
            super().save(*args, **kwargs)

    class Meta:
        abstract = True
        ordering = ["user__first_name", "user__last_name"]
