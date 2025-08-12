"""Core module for people."""

from datetime import date
from typing import Any, Dict, Tuple

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField


from app.people.utils import extract_id_num, mk_username, photo_upload_to
from app.shared.status.mixins import StatusableMixin


class PersonManager(models.Manager):
    """Custom creation Management."""

    USER_KWARGS = {
        "user",
        # "username",
        "password",
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "is_superuser",
        "is_active",
    }

    def _split_kwargs(
        self, kwargs: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Returns user_kwargs, person_kwargs."""
        user_kwargs = {k: kwargs.pop(k) for k in list(kwargs) if k in self.USER_KWARGS}
        return user_kwargs, kwargs

    def _create_user(self, **user_kwargs) -> User:
        """Create or get the User and set /update password."""
        password = user_kwargs.pop("password", None)
        username = user_kwargs.pop("username", "") or user_kwargs.pop("user").username

        user, created = User.create_user(
            username=username, password=password, **user_kwargs
        )
        # there some loop hole here
        if password and created:
            user.set_password(password)  # to make sure it is hashed
            user.save(update_fields=["password"])

        return user

    def _get_or_create(self, username, **user_kwargs) -> User:
        """Create or get the User and set /update password."""
        password = user_kwargs.pop("password", None)
        user, _ = User.objects.get_or_create(username=username, defaults=user_kwargs)
        # there some loop hole here
        if password:
            user.set_password(password)  # to make sure it is hashed
            user.save(update_fields=["password"])

        return user

    def _update_or_create(self, username, **user_kwargs) -> User:
        """Create or get the User and set /update password."""
        password = user_kwargs.pop("password", None)

        user, created = User.objects.update_or_create(
            username=username, defaults=user_kwargs
        )
        # there some loop hole here
        if password:
            user.set_password(password)  # to make sure it is hashed
            user.save(update_fields=["password"])

        return user

    def _get_username(self, **kwargs):
        """Look into the kwargs for elements to build the username."""
        username = kwargs.pop("username", "")
        if not username:
            first = kwargs.get("first_name", "")
            last = kwargs.get("last_name", "")
            username = mk_username(first, last, prefix_len=2)
        return username

    # public API ----------------------------------------------------
    def create(self, **kwargs):
        """Create a user and the person."""
        user_kwargs, person_kwargs = self._split_kwargs(kwargs)
        user = self._create_user(**user_kwargs)
        return super().create(user=user, **person_kwargs)

    def update_or_create(self, defaults, **kwargs):
        """Create a user and the person."""
        defaults = defaults or {}
        username = self._get_username(**defaults, **kwargs)
        user_kwargs, person_kwargs = self._split_kwargs(kwargs)
        user = self._update_or_create(username=username, **user_kwargs)

        return super().update_or_create(user=user, defaults=person_kwargs)

    def get_or_create(self, defaults, **kwargs):
        """Get or Create the user and the person."""
        defaults = defaults or {}
        username = self._get_username(**defaults, **kwargs)
        user_kwargs, person_kwargs = self._split_kwargs({**kwargs, **defaults})

        user = self._get_or_create(username=username, **user_kwargs)

        return super().get_or_create(user=user, defaults=person_kwargs)


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
    date_of_birth = models.DateField(_("date of birth"), null=True, blank=True)
    place_of_birth = models.CharField(blank=True)
    genre = models.CharField(choices=[("f", "Woman"), ("m", "Man")], blank=True)

    phone_number = PhoneNumberField(help_text="A Liberian phone number", blank=True)
    physical_address = models.TextField(
        help_text="eg. Tubman Town, Harper, Maryland", blank=True
    )

    # --- misc ---
    father_address = models.CharField(blank=True)
    father_name = models.CharField(blank=True)
    nationality = models.CharField(blank=True)
    origin = models.CharField(help_text="eg. Maryland, Nigeria", blank=True)
    bio = models.TextField(blank=True)
    photo = models.ImageField(upload_to=photo_upload_to, null=True, blank=True)
    marital_status = models.CharField(blank=True)

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
                # moins 1 ou 0, si the birthday has passed this year.
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

        if self.user_id:
            if self.GROUP:
                group, _ = Group.objects.get_or_create(name=self.GROUP)
                self.user.groups.add(group)

            if self.STAFF_STATUS is not None:
                self.user.is_staff = self.STAFF_STATUS
                self.user.save(update_fields=["is_staff"])

    @classmethod
    def mk_username(
        cls,
        first,
        last,
        middle=None,
        unique=True,
        exclude=None,
        prefix_len=None,
    ):
        """Defaut to make a user name.  Should be overridend by subclasses."""
        return mk_username(
            first,
            last,
            middle=middle if middle else "",
            exclude=exclude,
            unique=unique,
            prefix_len=prefix_len,
        )

    @classmethod
    def get_existing_id(cls) -> list[int]:
        """Returns the list of all existing number in the (class) ids field."""
        user_ids_str = cls.objects.values_list(cls.ID_FIELD or "", flat=True)  # type: ignore[attr-type]
        user_ids = [extract_id_num(v) for v in user_ids_str]
        return user_ids

    class Meta:
        abstract = True
        ordering = ["user__first_name", "user__last_name"]
