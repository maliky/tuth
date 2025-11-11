"""Staffs module."""
from datetime import date
from itertools import count
from typing import Self, cast

from django.contrib.auth import get_user_model
from django.db import models
from simple_history.models import HistoricalRecords


from app.academics.models.department import Department
from app.people.models.core import AbstractPerson
from app.people.utils import get_default_user

User = get_user_model()

DEFAULT_STAFF_ID = count(start=1, step=1)
DEFAULT_FACULTY_ID = count(start=1, step=1)


class Staff(AbstractPerson):
    """Base class for Staffs.

    Example:
        >>> Staff.objects.create(username=username, staff_id="ST01", department=dept)
        >>> staff_profile  # from tests.conftest
    Side Effects:
        save() from :class:AbstractPerson sets staff_id.
    """
    ID_FIELD = "staff_id"
    ID_PREFIX = "TU-STF"
    GROUP = "Staff"
    STAFF_STATUS = True

    # ~~~~~~~~ Mandatory ~~~~~~~~
    # ~~~~ Auto-filled ~~~~ /     # ~~~~ Read-only ~~~~
    staff_id = models.CharField(max_length=13, unique=True, editable=False)
    history = HistoricalRecords()
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
        return cast(Self, dft_staff)

    @classmethod
    def get_unique_default(cls) -> Self:
        """Return a unique default Staff."""
        return cls.get_default(staff_id=next(DEFAULT_STAFF_ID))

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user"], name="uniq_staff_per_user"),
        ]
