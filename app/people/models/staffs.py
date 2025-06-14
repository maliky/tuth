"""staffs module."""

# app/people/models/staffs.py

from typing import TYPE_CHECKING
from django.db import models
from django.db.models import QuerySet

from app.academics.models.curriculum import Curriculum
from app.people.models.core import AbstractPerson, UserDelegateMixin
from app.people.utils import mk_username, split_name
from app.shared.constants import TEST_PW
from app.shared.mixins import StatusableMixin
from django.contrib.auth.models import User

if TYPE_CHECKING:
    from app.academics.models.college import College

STAFF_ID_PREFIX = "TU_STF"


class Faculty(StatusableMixin, UserDelegateMixin, models.Model):
    staff_profile = models.OneToOneField("people.Staff", on_delete=models.CASCADE)
    college = models.ForeignKey("academics.College", on_delete=models.CASCADE)

    google_profile = models.URLField(blank=True)
    personal_website = models.URLField(blank=True)
    academic_rank = models.CharField(max_length=50, null=True, blank=True)
    # teaching load should be a function per semester or year
    # teaching_load = models.IntegerField()

    @property
    def curricula(self) -> QuerySet[Curriculum]:
        """
        Return all Curriculum instances in which this faculty is teaching.

        Traverses: Curriculum → courses → sections → session → faculty
        """
        return Curriculum.objects.filter(
            courses__sections__session__faculty=self
        ).distinct()

    def save(self, *args, **kwargs):
        assert (
            self.staff_profile is not None
        ), "Staff in the profil must be save before the Faculty. Check"
        super().save(*args, **kwargs)

    def _delegate_user(self):
        """Return the User instance we should forward to."""
        return self.staff_profile.user


class Staff(AbstractPerson):
    """Base class for Staffs."""

    staff_id = models.CharField(max_length=13, unique=True, editable=False)
    employment_date = models.DateField(null=True, blank=True)

    division = models.CharField(max_length=100, blank=True)

    # ! if talking of faculty they could be in different departments
    # ! would need a foreign key here
    department = models.CharField(max_length=100, blank=True)
    position = models.CharField(max_length=50, blank=True)

    def save(self, *args, **kwargs):

        assert self.user is not None, "User must be save before the staff."

        self.staff_id = self._mk_user_id(STAFF_ID_PREFIX)
        super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user"], name="uniq_staff_per_user"),
        ]


def ensure_faculty(name: str, college: "College") -> Faculty:
    """
    Return an existing or new Faculty for the given name and college.
    ! This can update the college.
    """
    _, first, _, last, _ = split_name(name)
    username = mk_username(first, last, unique=False)

    user, user_created = User.objects.get_or_create(
        username=username,
        defaults={"first_name": first, "last_name": last},
    )

    if user_created:
        user.set_password(TEST_PW)
        user.save()
        staff, _ = Staff.objects.get_or_create(user=user)
        faculty = Faculty.objects.create(staff_profile=staff, college=college)

        return faculty

    staff, _ = Staff.objects.get_or_create(user=user)

    faculty, faculty_created = Faculty.objects.get_or_create(
        staff_profile=staff, college=college
    )

    if faculty.college != college:
        faculty.college = college
        faculty.save()

    return faculty
