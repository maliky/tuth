"""Core module for people."""

# app/people/models/core.py

from datetime import date
from pathlib import Path

from app.people.utils import extract_id_num
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from app.shared.status.mixins import StatusableMixin

User = get_user_model()


def photo_upload_to(instance: "AbstractPerson", filename: str) -> str:
    """Store uploads under photos/<model>/<user-id>/<filename>."""
    _class = instance.__class__.__name__.lower()
    return str(Path("photos") / _class / str(instance.user_id) / filename)


class AbstractPerson(StatusableMixin, models.Model):
    """Base information shared by all people profiles.

    Student, Donor, Staff->Facutly
    Side Effects:
        save() assigns an ID derived from user.
    """

    ID_FIELD: str | None = None
    ID_PREFIX: str = "TU-"

    # ~~~~~~~~ Mandatory ~~~~~~~~
    # > this is redundant but mabye necessary
    # if I want to hide the User model from the common user.
    # first_name = models.CharField(blank=True)
    # last_name = models.CharField(blank=True)

    # ~~~~ Autofilled ~~~~
    # need to be filled automatically with the data from the first name, last name,
    # > I want the user to be created on the fly when I save this but
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="%(class)s",
        related_query_name="%(class)s",
    )
    # long_name = models.CharField(blank=False, editable=False)

    # ~~~~~~~~ Optional ~~~~~~~~
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

    # convenience for admin lists / logs
    def __str__(self) -> str:  # pragma: no cover
        return f"{self.long_name}"

    @property
    def long_name(self) -> str:
        """Set the long name from the different name parts."""
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

    @property
    def obj_id(self) -> str:
        """Returns the value of cls.id_prexix."""
        self._ensure_id_field_exists()
        objid = object.__getattribute__(self, self.ID_FIELD)  # type: ignore[arg-type]

        if objid is None:
            return ""

        return str(objid)

    # def _ensure_long_name(self) -> None:
    #     """Set the long name from the different name parts."""
    #     if not self.long_name:
    #         self.long_name = " ".join(
    #             [
    #                 self.name_prefix,
    #                 self.first_name,
    #                 self.middle_name,
    #                 self.last_name,
    #                 self.name_suffix,
    #             ]
    #         ).strip()

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

    def _must_exists_user(self) -> None:
        """Returns the user if it exists."""
        try:
            _ = self.user
        except User.DoesNotExist:
            raise ValidationError("User must have been saved at this point.")

    def _mk_id(self) -> str:
        """Build an ID incrementing the user_id depending on its class."""
        self._must_exists_user()

        if self.user.pk is None:
            raise ValidationError("Cannot generate Id if user.pk is None.")

        existing_ids = self.get_existing_id()
        if existing_ids:
            next_num = max(existing_ids) + 1
        else:
            next_num = 1

        return f"{self.ID_PREFIX}{next_num:05}"

    def _ensure_id_field_exists(self) -> None:
        """Raise an exception if ID_PREFIX is not set."""
        # > the check will not be detected by mypy. so ignore[arg-type]
        # would be good to find more clean to use mypy
        if not self.ID_FIELD:
            raise ValidationError("ID_FIELD needs to be set before creating new ID.")

    def _get_id_no(self) -> int | None:
        """Remove the ID_PREFIX and Returns the number associated with the id field."""
        objid = self.obj_id
        # the following suppose that after the prefix only numbers
        _, _, obj_no_str = objid.partition(self.ID_PREFIX)  # type: ignore[arg-type]
        return int(obj_no_str) if obj_no_str else 0

    def save(self, *args, **kwargs):
        """Create an ID and saves it for each model using _mk_id and ID_FIELD."""
        if not self.obj_id:
            new_id = self._mk_id()
            object.__setattr__(self, self.ID_FIELD, new_id)  # type: ignore[arg-type]
        super().save(*args, **kwargs)

    @classmethod
    def get_existing_id(cls) -> list[int]:
        """Returns the list of all existing number in the (class) ids field."""
        user_ids_str = cls.objects.values_list(cls.ID_FIELD, flat=True)  # type: ignore[attr-defined]
        user_ids = [extract_id_num(v) for v in user_ids_str]
        return user_ids

    class Meta:
        abstract = True
        ordering = ["user__first_name", "user__last_name"]
