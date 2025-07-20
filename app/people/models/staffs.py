"""staffs module."""

# app/people/models/staffs.py

from datetime import date
from itertools import count
from typing import Self

from app.shared.auth.perms import UserRole
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import QuerySet
from simple_history.models import HistoricalRecords

from app.academics.models.college import College
from app.academics.models.curriculum import Curriculum
from app.academics.models.department import Department
from app.people.models.core import AbstractPerson
from app.people.utils import get_default_user
from app.shared.status.mixins import StatusableMixin

User = get_user_model()

DEFAULT_STAFF_ID = count(start=1, step=1)
DEFAULT_FACULTY_ID = count(start=1, step=1)


class Staff(AbstractPerson):
    """Base class for Staffs.

    Example:
        >>> Staff.objects.create(user=user, staff_id="ST01", department=dept)
        >>> staff_profile  # from tests.conftest
    Side Effects:
        save() from :class:AbstractPerson sets staff_id.
    """

    ID_FIELD = "staff_id"
    ID_PREFIX = "TU-STF"
    GROUP = "staff"
    STAFF_STATUS = True
    
    # ~~~~~~~~ Mandatory ~~~~~~~~
    # ~~~~ Auto-filled ~~~~ /     # ~~~~ Read-only ~~~~
    staff_id = models.CharField(max_length=13, unique=True, editable=False)

    # ~~~~~~~~ Optional ~~~~~~~~
    employment_date = models.DateField(null=True, blank=True)

    # > need to model an organogram where I can add division & departments
    division = models.CharField(max_length=100, blank=True)
    # ! if talking of faculty they could be in different departments
    # ! would need a foreign key here
    department = models.ForeignKey(
        Department,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    position = models.CharField(max_length=50, blank=True)

    @classmethod
    def get_default(cls, staff_id: int = 0) -> Self:
        """Return a default Staff."""
        dft_staff, _ = cls.objects.get_or_create(
            staff_id=f"DFT_STF{staff_id:04d}",
            user=get_default_user(),
            employment_date=date.today(),
            department=Department.get_default(),
            position=f"Joker {staff_id:04d}",
        )
        return dft_staff

    @classmethod
    def get_unique_default(cls) -> Self:
        """Return a unique default Staff."""
        return cls.get_default(staff_id=next(DEFAULT_STAFF_ID))

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user"], name="uniq_staff_per_user"),
        ]


class Faculty(StatusableMixin, models.Model):
    """Teaching staff profile linked to a :class:Staff record.

    Example:
        >>> Faculty.objects.create(staff_profile=staff, college=college)
        >>> faculty_profile  # from tests.conftest

    Side Effects:
        save() assigns the default college when none is set.
    """

    GROUP = "faculty"
    STAFF_STATUS = True

    # ~~~~~~~~ Mandatory ~~~~~~~~
    staff_profile = models.OneToOneField("people.Staff", on_delete=models.CASCADE)
    # ~~~~ Auto-filled ~~~~
    history = HistoricalRecords()

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
        return dft_faculty

    @classmethod
    def get_unique_default(cls) -> Self:
        """Returns a unique default Faculty."""
        unique_profile = Staff.get_unique_default()
        return cls.get_default(unique_profile)

    class Meta:
        verbose_name = "Faculty"
        verbose_name_plural = "Faculty profiles"
