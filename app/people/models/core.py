"""Core module for people."""

from datetime import date
import logging
from pathlib import Path

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField

from app.people.models.object_manager import PersonManager
from app.people.utils import extract_id_num, mk_username, photo_upload_to

logger = logging.getLogger(__name__)


class AbstractPerson(models.Model):
    """Base information shared by all people profiles.

    Student, Donor, Staff->Facutly
    Side Effects:
        save() assigns an ID derived from user.

    https://docs.djangoproject.com/en/5.2/topics/auth/customizing/#specifying-custom-user-model
    # https://docs.djangoproject.com/en/5.2/topics/auth/customizing/#django.contrib.auth.models.AbstractUser

    """

    class Meta:
        abstract = True
        ordering = ["user__first_name", "user__last_name"]

    ID_FIELD: str | None = None
    ID_PREFIX: str = "TU-"
    EMAIL_SUFFIX: str = "@tubmanu.edu.lr"
    GROUP: str | None = None
    STAFF_STATUS: bool = False

    # ~~~~~~~~ Mandatory ~~~~~~~~
    objects = PersonManager()
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="%(class)s",
        related_query_name="%(class)s",
        blank=True,
    )
    # ~~~~ Autofilled ~~~~
    long_name = models.CharField(editable=False)
    username = models.CharField(editable=True)
    email = models.EmailField(editable=True)

    # ~~~~~~~~ Optional ~~~~~~~~
    # # need to define a list of choice well structured
    middle_name = models.CharField(blank=True)
    name_prefix = models.CharField(help_text="eg. 'Miss.'", blank=True)
    name_suffix = models.CharField(help_text="eg. 'Phd.'", blank=True)
    birth_date = models.DateField(_("date of birth"), null=True, blank=True)
    birth_place = models.CharField(blank=True)
    gender = models.CharField(choices=[("f", "Female"), ("m", "Male")], blank=True)

    phone_number = PhoneNumberField(help_text="A Liberian phone number", blank=True)
    physical_address = models.TextField(
        help_text="eg. Tubman Town, Harper, Maryland", blank=True
    )

    # --- misc ---
    # > Why do I have father adress for an Abstract Person ? already covered by student
    # father_address = models.CharField(blank=True)
    # father_name = models.CharField(blank=True)
    nationality = models.CharField(blank=True)
    origin_county = models.CharField(help_text="eg. Maryland, Nigeria", blank=True)
    bio = models.TextField(blank=True)
    photo = models.ImageField(upload_to=photo_upload_to, null=True, blank=True)
    marital_status = models.CharField(blank=True)

    # convenience for admin lists / logs
    def __str__(self) -> str:  # pragma: no cover
        return f"{self.long_name} ({self.obj_id})"

    @property
    def age(self) -> int | None:
        """Compute and returns the age of the abstract user."""
        if not self.birth_date:
            return None
        today = date.today()
        has_had_birthday = (today.month, today.day) >= (
            self.birth_date.month,
            self.birth_date.day,
        )
        return today.year - self.birth_date.year - (0 if has_had_birthday else 1)

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
        self.user.email = self.email
        self.user.save(update_fields=["email"])

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
        current_username = self.user.username or ""
        desired_username = current_username or self.mk_username(
            self.user.first_name,
            self.user.last_name,
            middle=self.middle_name,
            unique=False,
        )
        username = desired_username
        counter = 1
        while (
            username
            and User.objects.filter(username=username).exclude(pk=self.user.pk).exists()
        ):
            counter += 1
            username = f"{desired_username}{counter}"

        if username and username != current_username:
            self.user.username = username
            self.user.save(update_fields=["username"])

        if not self.user.username:
            raise ValidationError("A username should exists.")
        self.username = self.user.username

    def _ensure_email(self):
        """Create a model field matching the email field for admin."""
        self._ensure_username()

        if self.user.email:
            self.email = self.user.email
        else:
            self.email = self.mk_email()
            self.user.email = self.email
            self.user.save(update_fields=["email"])

    def set_password(self, password):
        """Setting password for the attached user."""
        self._ensure_user()
        self.user.set_password(password)
        self.user.save()

    def mk_email(self, username=None):
        """Create an email foe the abstract and the user using subclass suffix."""
        if not username:
            username = self.username or self.user.username
        return slugify(username, allow_unicode=False).replace("-", "") + self.EMAIL_SUFFIX

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

    def roles(self) -> str:
        """Returns the list of the user's groups."""
        names = self.user.groups.values_list("name", flat=True)
        return ", ".join(names) if names else ""

    def save(self, *args, **kwargs):
        """Create an ID and saves it for each model using _mk_id and ID_FIELD."""
        if not self.obj_id:
            new_id = self._mk_id()
            object.__setattr__(self, self.ID_FIELD, new_id)  # type: ignore[arg-type]

        self._ensure_long_name()
        self._ensure_email()
        self._ensure_username()
        super().save(*args, **kwargs)

        # handling groups
        if self.user_id:
            if self.GROUP:  # each person is part of a GROUP
                group, _ = Group.objects.get_or_create(name=self.GROUP)
                self.user.groups.add(group)

            if self.STAFF_STATUS:
                self.user.is_staff = self.STAFF_STATUS
                self.user.save(update_fields=["is_staff"])

    @classmethod
    def mk_username(
        cls, first, last, middle="", unique=True, exclude=None, prefix_len=None, sep=None
    ):
        """Defaut to make a user name.  Should be overridend by subclasses."""
        return mk_username(
            first,
            last,
            middle=middle,
            exclude=exclude,
            unique=unique,
            prefix_len=prefix_len,
            sep=sep,
        )

    @classmethod
    def get_existing_id(cls) -> list[int]:
        """Returns the list of all existing number in the (class) ids field."""
        user_ids_raw = cls.objects.values_list(
            "pk",
            cls.ID_FIELD or "",
        )  # type: ignore[attr-type]
        user_ids: list[int] = []
        for pk, val in user_ids_raw:
            try:
                user_ids.append(extract_id_num(val))
            except ValidationError:
                _log_invalid_id(cls.__name__, pk, val)
        return user_ids


def _log_invalid_id(model_name: str, pk: int, id_value: str) -> None:
    """Record an invalid ID in both logs and a sidecar CSV, then continue."""
    logger.warning(
        "Skipping invalid ID while computing next ID",
        extra={"id_value": id_value, "model": model_name, "pk": pk},
    )
    tmp_dir = Path("Seed_data/Tmp")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    path = tmp_dir / "invalid_ids.csv"
    header = "model,pk,id_value\n"
    line = f"{model_name},{pk},{id_value}\n"
    if not path.exists():
        path.write_text(header + line, encoding="utf-8")
    else:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line)
