"""staffs module."""

# app/people/models/staffs.py

from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import QuerySet

from app.academics.models.college import College
from app.academics.models.curriculum import Curriculum
from app.academics.models.department import Department
from app.people.models.core import AbstractPerson
from app.people.utils import mk_username, split_name
from app.shared.constants import TEST_PW
from app.shared.mixins import StatusableMixin

User = get_user_model()


class Faculty(StatusableMixin, models.Model):
    """Instructor profile linked to a staff member.

    Example:
        >>> faculty_profile  # from tests.conftest
    """

    staff_profile = models.OneToOneField("people.Staff", on_delete=models.CASCADE)

    # Rattachement College but could have many more
    # > needs to be changed to ManyToMany
    college = models.ForeignKey(
        "academics.College", on_delete=models.CASCADE, null=True, blank=True
    )

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

    @property
    def staff_id(self):
        return self.staff_profile.staff_id

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.staff_profile}"

    def save(self, *args, **kwargs):
        assert (
            self.staff_profile is not None
        ), "Staff profil must be save before the Faculty. Check"
        try:
            _ = self.college
        except College.DoesNotExist:
            college, college_created = College.objects.get_or_create(code="COAS")
            self.college = college

        if not self.college_id:  # ← check for NULL / missing FK
            self.college, _ = College.objects.get_or_create(code="COAS")
        super().save(*args, **kwargs)

    def _delegate_user(self):
        """Return the User instance we should forward to."""
        return self.staff_profile.user

    class Meta:
        verbose_name = "Faculty"
        verbose_name_plural = "Faculty profiles"


class Staff(AbstractPerson):
    """Base class for Staffs.

    Example:
        >>> staff_profile  # from tests.conftest
    """

    ID_FIELD = "staff_id"
    ID_PREFIX = "TU_STF"

    staff_id = models.CharField(max_length=13, unique=True, editable=False)
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
