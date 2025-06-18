"""people Student module."""

# app/people/models/student.py

from __future__ import annotations

from app.people.models.core import AbstractPerson
from django.db import models


from app.timetable.models.semester import Semester


class Student(AbstractPerson):
    """Extra academic information for enrolled students.

    Example:
        >>> from app.people.models import Student
        >>> user = User.objects.create_user(username="stud")
        >>> s = Student.objects.create(user=user, enrollment_semester=semester)
        >>> s.student_id  # auto-set from user id
        'TU_STD0001'
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

    enrollment_semester = models.ForeignKey(
        Semester,
        on_delete=models.PROTECT,
    )
    enrollment_date = models.DateField(null=True, blank=True)

    # > need to create a method to compute le level of the student based on the
    # > number of credit completed
    # def credit_completed(self) -> int:
    #     self.courses.credit

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user"], name="uniq_student_per_user"),
        ]
