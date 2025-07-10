"""Core module for people."""

from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField

from app.people.utils import extract_id_num, mk_username, photo_upload_to
from app.shared.status.mixins import StatusableMixin

User = get_user_model()


class AbstractPerson(StatusableMixin, models.Model):
    """Base information shared by all people profiles.

    Student, Donor, Staff->Facutly
    Side Effects:
        save() assigns an ID derived from user.

    https://docs.djangoproject.com/en/5.2/topics/auth/customizing/#specifying-custom-user-model
    # https://docs.djangoproject.com/en/5.2/topics/auth/customizing/#django.contrib.auth.models.AbstractUser

    """

    ID_FIELD: str | None = None
    ID_PREFIX: str = "TU-"
    EMAIL_SUFFIX: str = "@tubmanu.edu.lr"

    # ~~~~~~~~ Mandatory ~~~~~~~~
    # ~~~~ Autofilled ~~~~
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="%(class)s",
        related_query_name="%(class)s",
        blank=True,
    )
    long_name = models.CharField(editable=False)
    username = models.CharField(editable=True)
    email = models.EmailField(editable=True)
    # ~~~~~~~~ Optional ~~~~~~~~
    # # need to define a list of choice well structured
    middle_name = models.CharField(blank=True)
    name_prefix = models.CharField(help_text="eg. 'Miss.'", blank=True)
    name_suffix = models.CharField(help_text="eg. 'Phd.'", blank=True)
    date_of_birth = models.DateField(_("date of birth"), null=True, blank=True)

    phone_number = PhoneNumberField(help_text="A Liberian phone number", blank=True)
    physical_address = models.TextField(help_text="eg. Tubman Town, Harper, Maryland", blank=True)

    # --- misc ---
    bio = models.TextField(blank=True)
    photo = models.ImageField(upload_to=photo_upload_to, null=True, blank=True)

    # convenience for admin lists / logs
    def __str__(self) -> str:  # pragma: no cover
        return f"{self.long_name} ({self.obj_id})"

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
    def obj_id(self) -> str:
        """Returns the value of cls.id_prexix."""
        self._is_id_field()
        objid = object.__getattribute__(self, self.ID_FIELD)  # type: ignore[arg-type]

        if objid is None:
            return ""

        return str(objid)

    def _update_email(self) -> None:
        """Update the user email."""
        self._ensure_username()
        self.email = self.mk_email()

    def _update_username(self) -> None:
        """Update the user username."""
        self._ensure_username()
        self.email = self.mk_email()

    def _update_long_name(self) -> None:
        """Update the long name."""
        self.long_name = " ".join(
            [
                self.name_prefix,
                self.user.first_name,
                self.middle_name,
                self.user.last_name,
                self.name_suffix,
            ]
        ).strip()

    def _ensure_long_name(self) -> None:
        """Set the long name from the different name parts."""
        self._ensure_user()
        if not self.long_name:
            self._update_long_name()

    def _ensure_user(self):
        """Make sure the user exsits."""
        if not self._exists_user():
            raise ValidationError("A user must exists.")

    def _exists_user(self) -> bool:
        """Returns the user if it exists."""
        try:
            _ = self.user
            return True
        except User.DoesNotExist:
            return False

    def _ensure_username(self):
        """Create a model field matching the user field for admin."""
        self._ensure_user()
        if self.user.username:
            self.username = self.user.username
        else:
            # Should never get here because username is mandatory for a user.
            raise ValidationError("A username should exists.")

    def _ensure_email(self):
        """Create a model field matching the email field for admin."""
        self._ensure_username()

        if self.user.email:
            self.email = self.user.email
        else:
            self.mk_email(self.username)

    def mk_email(self, username=None):
        """Create an email foe the abstract and the user using subclass suffix."""
        if not username:
            username = self.username or self.user.username
        return slugify(username, allow_unicode=False).replace("-", "") + self.EMAIL_SUFFIX

    def mk_username(self, first=None, last=None, middle=None, unique=True):
        """Defaut to make a user name.  Should be overridend by subclasses."""
        return mk_username(
            self.user.first_name if not first else first,
            self.user.last_name if not last else last,
            middle="" if not middle else middle,
            unique=unique,
        )

    def _mk_id(self) -> str:
        """Build an ID incrementing the user_id depending on its class."""
        existing_ids = self.get_existing_id()

        next_num = max(existing_ids) + 1 if existing_ids else 1

        return f"{self.ID_PREFIX}{next_num:05}"

    def _is_id_field(self) -> None:
        """Raise an exception if ID_PREFIX is not set."""
        if not self.ID_FIELD:
            raise ValidationError("ID_FIELD needs to be set before creating new ID.")

    def _get_id_no(self) -> int | None:
        """Remove the ID_PREFIX and Returns the number associated with the id field."""
        objid = self.obj_id

        # the following suppose that after the prefix str there's only numbers.
        _, _, obj_no_str = objid.partition(self.ID_PREFIX)  # type: ignore[arg-type]

        return int(obj_no_str) if obj_no_str else 0

    def save(self, *args, **kwargs):
        """Create an ID and saves it for each model using _mk_id and ID_FIELD."""
        if not self.obj_id:
            new_id = self._mk_id()
            object.__setattr__(self, self.ID_FIELD, new_id)  # type: ignore[arg-type]

        self._ensure_long_name()
        self._ensure_email()
        self._ensure_username()
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
