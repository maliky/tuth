"""Faculty class."""

from typing import Any, Dict, Self, Tuple, cast

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import QuerySet

from app.academics.models.college import College
from app.academics.models.curriculum import Curriculum
from app.people.models.staffs import Staff
from app.shared.status.mixins import StatusableMixin


class FacultyManager(models.Manager):
    """Custom creation Management."""

    STAFF_KWARGS = {
        # ~~~~ Staff.Userfields ~~~~
        "username",
        "password",
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "is_superuser",
        "is_active",
        # ~~~~ Staff only fields ~~~~
        # "staff_profile",
        "history",
        "google_profile",
        "personal_website",
        "academic_rank",
        "middle_name",
        "name_prefix",
        "name_suffix",
    }

    def _split_kwargs(
        self, kwargs: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Returns staff_kwargs, faculty_kwargs."""
        staff_kwargs = {k: kwargs.pop(k) for k in list(kwargs) if k in self.STAFF_KWARGS}
        return staff_kwargs, kwargs

    # public API ----------------------------------------------------
    def create(self, **kwargs):
        """Create a staff and the faculty."""
        staff_kwargs, faculty_kwargs = self._split_kwargs(kwargs)
        staff_profile = Staff.objects.create(**staff_kwargs)
        return super().create(staff_profile=staff_profile, **faculty_kwargs)

    def get_or_create(self, defaults=None, **kwargs):
        """Get or Create the Faculty and create the Staff if id does not exists."""
        defaults = defaults or {}
        username = kwargs.pop("username")
        staff_kwargs, faculty_kwargs = self._split_kwargs({**kwargs, **defaults})
        staff_profile, _ = Staff.objects.get_or_create(
            username=username, defaults=staff_kwargs
        )
        return super().get_or_create(staff_profile=staff_profile, defaults=faculty_kwargs)


class Faculty(StatusableMixin, models.Model):
    """Teaching staff profile linked to a :class:Staff record.

    Example:
        >>> Faculty.objects.create(staff_profile=staff, college=college)
        >>> faculty_profile  # from tests.conftest

    Side Effects:
        save() assigns the default college when none is set.
    """

    GROUP = "Faculty"
    STAFF_STATUS = True

    # ~~~~~~~~ Mandatory ~~~~~~~~
    staff_profile = models.OneToOneField("people.Staff", on_delete=models.CASCADE)
    # ~~~~ Auto-filled ~~~~

    objects = FacultyManager()  # manage queries

    # ~~~~ Optional ~~~~
    # Main college for the faculty (Could be a department also)
    # just for administrative convieniance
    college = models.ForeignKey(
        "academics.College", on_delete=models.CASCADE, null=True, blank=True
    )
    # We can get all the colleges of the facutly via section->Program->..
    google_profile = models.URLField(blank=True)
    personal_website = models.URLField(blank=True)
    academic_rank = models.CharField(max_length=50, null=True, blank=True)

    # teaching load should be a function per semester or year
    # teaching_load = models.IntegerField()

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.staff_profile}"

    @property
    def curricula(self) -> QuerySet[Curriculum]:
        """Return all Curriculum instances in which this faculty is teaching.

        Traverses: Curriculum → courses → sections → session → faculty
        """
        return Curriculum.objects.filter(
            courses__sections__session__faculty=self
        ).distinct()

    @property
    def staff_id(self):
        """Get the staff id."""
        return self.staff_profile.staff_id

    def get_division(self):
        """Returns the faculty division."""
        return self.staff_profile.division

    def get_department(self):
        """Returns the faculty division."""
        return self.staff_profile.department

    def username(self):
        """Returns the username attached to the staff_profile."""
        return self.staff_profile.username

    def _ensure_college(self):
        """Make sure we have a college."""
        if not self.college_id:
            self.college = College.get_default()

    def save(self, *args, **kwargs):
        """Check that we have a college for the staff before save."""
        if self.staff_profile is None:
            raise ValidationError("Staff profile must be save before the Faculty.")

        self._ensure_college()
        super().save(*args, **kwargs)

    def _delegate_user(self):
        """Return the User instance we should forward to."""
        return self.staff_profile.user

    @classmethod
    def get_default(cls, profile=None) -> Self:
        """Returns a default Faculty."""
        if not profile:
            profile = Staff.get_default()
        college = College.get_default()
        dft_faculty, _ = cls.objects.get_or_create(staff_profile=profile, college=college)

        return cast(Self, dft_faculty)

    @classmethod
    def get_unique_default(cls) -> Self:
        """Returns a unique default Faculty."""
        unique_profile = Staff.get_unique_default()
        return cls.get_default(unique_profile)

    class Meta:
        verbose_name = "Faculty"
        verbose_name_plural = "Faculty profiles"
