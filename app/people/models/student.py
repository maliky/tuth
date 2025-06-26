"""people Student module."""

# app/people/models/student.py

from __future__ import annotations

from app.academics.models.curriculum import Curriculum
from app.people.models.core import AbstractPerson
from django.db import models


from app.timetable.models.semester import Semester


class Student(AbstractPerson):
    """Extra academic information for enrolled students.

    Example:
        >>> user = User.objects.create_user(username="stud")
        >>> s = Student.objects.create(user=user, current_enroled_semester=semester)
        >>> s.student_id  # auto-set from user id
        'TU_STD0001'
    Side Effects:
        save() from :class:AbstractPerson populates student_id.
    """

    ID_FIELD = "student_id"
    ID_PREFIX = "TU_STD"

    student_id = models.CharField(max_length=20, unique=True)
    curriculum = models.ForeignKey(
        "academics.Curriculum", on_delete=models.SET_NULL, null=True, blank=True
    )
    current_enroled_semester = models.ForeignKey(
        Semester,
        on_delete=models.PROTECT,
        null=True,
    )
    first_enrollement_date = models.DateField(null=True, blank=True)

    def __str__(self):
        """Show the student id, name and user name."""
        ret = f"{self.student_id}"
        if self.user:
            ret += f"- {self.user}: {self.user.username}"
        return ret

    # > need to create a method to compute le level of the student based on the
    # > number of credit completed
    # def credit_completed(self) -> int:
    #     self.courses.credit
    @property
    def college(self):
        """Retunrs the Student current college."""
        self.curriculum.college

    def save(self, *args, **kwargs):
        """Make sure we have a curriculum for all students."""
        # import ipdb; ipdb.set_trace()

        if not self.curriculum:
            self.curriculum = Curriculum.get_default()
        super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user"], name="uniq_student_per_user"),
        ]
