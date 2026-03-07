"""people Student module."""

# app/people/models/student.py

from __future__ import annotations

from typing import cast

from django.contrib.auth.models import User
from django.db import models
from django.db.models import Sum
from simple_history.models import HistoricalRecords

from app.academics.choices import LEVEL_NUMBER
from app.academics.constants import MAX_STUDENT_CREDITS
from app.academics.models.course import Course
from app.academics.models.curriculum_course import CurriCrs

from app.academics.models.curriculum import Curriculum
from app.people.models.core import AbstractPerson
from app.people.models.student_curriculum_enrollment import (
    get_primary_curriculum,
    set_primary_std_curri_enroll,
    sync_primary_std_curri_enroll,
)
from app.shared.mixins import SimpleTableMixin
from app.shared.types import CrsQuery
from app.timetable.models.semester import Semester


class Student(AbstractPerson):
    """Extra academic information for enrolled students.

    Example:
        >>> user = User.objects.create_user(username="stud")
        >>> s = Student.objects.create(
        ...     username=username,
        ...
    last_enrolled_semester=semester,
        ... )
        >>> s.student_id  # auto-set from user id
        'TU_STD0001'
    Side Effects:
        save() from :class:AbstractPerson populates student_id.
    """

    ID_FIELD = "student_id"
    ID_PREFIX = "TU-STD"
    EMAIL_SUFFIX = ".stud@tubmanu.edu.lr"
    GROUP = "Student"  # must match the UserRole Gps
    STAFF_STATUS = False

    # ~~~~~~~~ Mandatory ~~~~~~~~
    curricula = models.ManyToManyField(
        "academics.Curriculum",
        through="people.StdCurriEnroll",
        related_name="enrolled_students",
        blank=True,
    )
    history = HistoricalRecords()

    # ~~~~ Auto-filled ~~~~
    student_id = models.CharField(max_length=20, unique=True, blank=True)

    # ~~~~~~~~ Optional ~~~~~~~~
    last_enrolled_semester = models.ForeignKey(
        Semester,
        on_delete=models.PROTECT,
        null=True,
        related_name="current_stds",
    )

    entry_semester = models.ForeignKey(
        Semester,
        on_delete=models.PROTECT,
        null=True,
        related_name="students_entered",
    )
    # Updated each semester by staff to cap registration credit load.
    max_credit_hours = models.PositiveSmallIntegerField(
        default=MAX_STUDENT_CREDITS,
    )
    last_school_attended = models.CharField(blank=True)
    reason_for_leaving = models.CharField(blank=True)
    father_name = models.CharField(blank=True)
    father_address = models.CharField(blank=True)
    mother_name = models.CharField(blank=True)
    mother_address = models.CharField(blank=True)
    emergency_contact = models.CharField(blank=True)

    # ~~~~~~~~~~~~~~~~ Reverse ~~~~~~~~~~~~~~~~
    # Document.student_set ?

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
        return self.primary_curriculum.college

    @property
    def primary_curriculum(self) -> Curriculum:
        """Return the student's canonical curriculum from enrollment rows."""
        return get_primary_curriculum(self)

    @primary_curriculum.setter
    def primary_curriculum(self, curriculum: Curriculum) -> None:
        """Set the canonical curriculum through StdCurriEnroll."""
        # Keep assignment until save() reconciles enrollment rows.
        self._pending_primary_curriculum = curriculum  # type: ignore[attr-defined]

    def passed_crss(self) -> CrsQuery:
        """Return courses the student completed with a passing grade."""
        return Course.objects.filter(
            in_curriculum_courses__sections__grade__student=self,
            # GradeType.number >= 1 == passing grade
            in_curriculum_courses__sections__grade__value__number__gte=1,
        ).distinct()

    @property
    def completed_credits(self) -> int:
        """Return sum of credit hours successfully completed."""
        curriculum = self.primary_curriculum
        passed_ids = self.passed_crss().values_list("id", flat=True)
        agg = CurriCrs.objects.filter(
            curriculum=curriculum, course_id__in=passed_ids
        ).aggregate(total=Sum("credit_hours"))
        return agg.get("total") or 0

    @property
    def class_level(self) -> str:
        """Return student level computed from completed credits."""
        credits = self.completed_credits
        if credits <= 36:
            return LEVEL_NUMBER.ONE.label
        if credits <= 72:
            return LEVEL_NUMBER.TWO.label
        if credits <= 108:
            return LEVEL_NUMBER.THREE.label
        return LEVEL_NUMBER.FOUR.label

    def allowed_crss(self) -> CrsQuery:
        """Return courses available for registration based on prerequisites."""
        curriculum = self.primary_curriculum
        all_courses = Course.for_curri(curriculum)
        passed = self.passed_crss()
        allowed_ids: list[int] = []
        passed_ids = set(passed.values_list("id", flat=True))

        for course in all_courses.exclude(id__in=passed_ids):
            # > do not uncommnent below. I need to solve the
            # > prerequisits firsts.
            # req_ids = course.course_prereq_edges.filter(
            #     curriculum=curriculum
            # ).values_list("prerequisite_course_id", flat=True)
            # if all(req_id in passed_ids for req_id in req_ids):
            #     allowed_ids.append(course.id)
            allowed_ids.append(course.id)

        return Course.objects.filter(id__in=allowed_ids)

    @classmethod
    def allowed_crssmk_username(
        cls,
        first,
        last,
        middle=None,
        unique=None,
        exclude=None,
        prefix_len=None,
        sep=None,
    ):
        """Define the standard way to create student username.

        The difference with other username is that we take in account,
        the middle name inital and use the first 3 letters of the first name.
        As usual should be unique
        """
        return super().mk_username(
            first, last, middle=middle, exclude=exclude, prefix_len=prefix_len, sep=sep
        )

    def save(self, *args, **kwargs):
        """Make sure we have a canonical enrollment row for all students.

        When a student's enrollment is confirmed for the first time
        (i.e., ``last_enrolled_semester`` is set) and the
        ``entry_semester`` is empty, record today's date.
        """
        super().save(*args, **kwargs)
        self._ensure_primary_curri_enrollment()

    def _ensure_primary_curri_enrollment(self) -> None:
        """Keep enrollment rows canonical after student save."""
        pending_curriculum = cast(
            Curriculum | None,
            getattr(self, "_pending_primary_curriculum", None),
        )
        if pending_curriculum is not None:
            set_primary_std_curri_enroll(
                self,
                pending_curriculum,
                entry_semester_id=self.entry_semester_id,
                is_active=True,
            )
            if hasattr(self, "_pending_primary_curriculum"):
                delattr(self, "_pending_primary_curriculum")
            return
        sync_primary_std_curri_enroll(self)

    @classmethod
    def get_dft(cls) -> "Student":
        """Return a placeholder Student used for legacy imports."""
        user, _ = User.objects.get_or_create(
            username="default_student",
            defaults={"first_name": "Default", "last_name": "Student"},
        )
        student, _ = cls.objects.get_or_create(
            user=user,
            defaults={
                "student_id": "TU-DFT",
            },
        )
        set_primary_std_curri_enroll(
            student,
            Curriculum.get_dft(),
            entry_semester_id=student.entry_semester_id,
            is_active=True,
        )
        return cast("Student", student)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user"], name="uniq_student_per_user"),
        ]
