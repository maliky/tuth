"""others module."""

# app/people/models/others.py

from __future__ import annotations


# from app import academics
from app.people.models.core import AbstractPerson
from django.db import models


DONOR_ID_PREFIX = "TU_DNR"
STUDENT_ID_PREFIX = "TU_STD"


class Donor(AbstractPerson, models.Model):
    """Contact information for donors supporting students."""

    donor_id = models.CharField(max_length=13, unique=True, editable=False)

    def save(self, *args, **kwargs):
        assert (
            self.user is not None
        ), f"User must be saved before the Donor. Check {self.user}."
        self.donor_id = self._mk_user_id(DONOR_ID_PREFIX)
        super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user"], name="uniq_donor_per_user"),
        ]


class Student(AbstractPerson):
    """Extra academic information for enrolled students."""

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
    enrollment_semester = models.PositiveSmallIntegerField()
    enrollment_date = models.DateField(null=True, blank=True)

    # > need to create a method to compute le level of the student based on the number
    # of credit completed
    # def credit_completed(self) -> int:
    #     self.courses.credit

    def save(self, *args, **kwargs):
        assert (
            self.user is not None
        ), f"User must be saved before the Student. Check {self.user}."
        self.student_id = self._mk_user_id(STUDENT_ID_PREFIX)
        super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user"], name="uniq_student_per_user"),
        ]
