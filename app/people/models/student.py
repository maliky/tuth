"""people Student module."""

# app/people/models/student.py

from __future__ import annotations

from django.db import models

from app.academics.models.course import Course
from app.academics.models.curriculum import Curriculum
from app.people.models.core import AbstractPerson
from app.shared.types import CourseQuery
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
    ID_PREFIX = "TU-STD"
    EMAIL_SUFFIX = ".stud@tubmanu.edu.lr"

    # ~~~~~~~~ Mandatory ~~~~~~~~
    curriculum = models.ForeignKey("academics.Curriculum", on_delete=models.CASCADE)

    # ~~~~ Auto-filled ~~~~
    student_id = models.CharField(max_length=20, unique=True, blank=True)

    # ~~~~~~~~ Optional ~~~~~~~~
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
            ret = f"{self.long_name} ({self.username})"
        return ret

    # > need to create a method to compute le level of the student based on the
    # > number of credit completed
    # def credit_completed(self) -> int:
    #     self.courses.credit
    @property
    def college(self):
        """Return the student's current college."""
        return self.curriculum.college

    def passed_courses(self) -> CourseQuery:
        """Return courses the student completed with a passing grade."""
        return Course.objects.filter(
            in_programs__sections__grade__student=self,
            # GradeType.number >= 1 == passing grade
            in_programs__sections__grade__grade__number__gte=1,
        ).distinct()

    def allowed_courses(self) -> CourseQuery:
        """Return courses available for registration based on prerequisites."""
        curriculum = self.curriculum or Curriculum.get_default()
        all_courses = Course.for_curriculum(curriculum)
        passed = self.passed_courses()
        allowed_ids: list[int] = []
        passed_ids = set(passed.values_list("id", flat=True))
        for course in all_courses.exclude(id__in=passed_ids):
            req_ids = course.course_prereq_edges.filter(
                curriculum=curriculum
            ).values_list("prerequisite_course_id", flat=True)
            if all(req_id in passed_ids for req_id in req_ids):
                allowed_ids.append(course.id)
        return Course.objects.filter(id__in=allowed_ids)

    def save(self, *args, **kwargs):
        """Make sure we have a curriculum for all students."""

        if not self.curriculum_id:
            self.curriculum = Curriculum.get_default()
        super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user"], name="uniq_student_per_user"),
        ]
