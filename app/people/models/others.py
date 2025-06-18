"""others people module."""

# app/people/models/others.py

from __future__ import annotations

from django.db import models

from app.people.models.core import AbstractPerson
from app.timetable.models.semester import Semester


class Donor(AbstractPerson):
    """Contact information for donors supporting students.

    Example:
        >>> from app.people.models import Donor
        >>> Donor.objects.create(user=user, donor_id="DN001")

    Side Effects:
        ``save()`` from :class:`AbstractPerson` populates ``donor_id``.
    """

    ID_FIELD = "donor_id"
    ID_PREFIX = "TU_DNR"

    donor_id = models.CharField(max_length=13, unique=True, editable=False, blank=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user"], name="uniq_donor_per_user"),
        ]


class Student(AbstractPerson):
    """Extra academic information for enrolled students.

    Example:
        >>> from app.people.models import Student
        >>> Student.objects.create(user=user, student_id="ST001", enrollment_semester=semester)

    Side Effects:
        ``save()`` from :class:`AbstractPerson` populates ``student_id``.
    """

    ID_FIELD = "student_id"
    ID_PREFIX = "TU_STD"

    student_id = models.CharField(max_length=20, unique=True)

    # academics
    college = models.ForeignKey(
        "academics.College", on_delete=models.SET_NULL, null=True, blank=True
    )
    curriculum = models.ForeignKey(
        "academics.Curriculum", on_delete=models.SET_NULL, null=True, blank=True
    )

    # > This should an semester. Can be any of 1 or 2
    # > update this field with FK
    enrollment_semester = models.ForeignKey(
        Semester,
        on_delete=models.PROTECT,
    )
    enrollment_date = models.DateField(null=True, blank=True)

    # > need to create a method to compute le level of the student based on the number
    # of credit completed
    # def credit_completed(self) -> int:
    #     self.courses.credit

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user"], name="uniq_student_per_user"),
        ]
