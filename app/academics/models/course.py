"""Course module."""

from __future__ import annotations

from itertools import count
from typing import Optional, Self

from django.apps import apps
from django.db import models
from simple_history.models import HistoricalRecords

from app.academics.choices import LEVEL_NUMBER
from app.academics.models.curriculum import Curriculum
from app.academics.models.department import Department
from app.shared.models import CreditHour
from app.shared.types import CourseQuery
from app.shared.utils import make_course_code
from app.timetable.utils import get_current_semester

DEFAULT_COURSE_NO = count(start=1, step=1)


class Course(models.Model):
    """University catalogue entry describing a single course offering.

    Example:
        >>> COAS = College.get_default()
        >>> MATH = Departement.objects.create(code="COAS", long_name="College of Arts and Sciences")
        >>> Course.objects.create(name="MATH", number="101", title="Algebra", college=coas)

    Side Effects:
        save() populates code from name and number.
    """

    # ~~~~~~~~ Mandatory ~~~~~~~~
    number = models.CharField(max_length=10)  # e.g. 101

    # ~~~~ Auto-filled ~~~~
    department = models.ForeignKey(
        "academics.Department",
        on_delete=models.CASCADE,
        related_name="courses",
    )
    history = HistoricalRecords()
    # ~~~~ Read-only ~~~~
    code = models.CharField(max_length=20, editable=False)

    # ~~~~~~~~ Optional ~~~~~~~~
    short_code = models.CharField(max_length=20, editable=True, null=True, blank=True)
    title = models.CharField(max_length=255, blank=True, null=True)
    description: models.TextField = models.TextField(blank=True, null=True)
    prerequisites = models.ManyToManyField(
        "self",
        symmetrical=False,
        through="academics.Prerequisite",
        related_name="dependent_courses",
        blank=True,
    )

    def __str__(self) -> str:  # pragma: no cover
        """Return the CODE - Title representation."""
        title = f" - {self.title}" if self.title else ""
        return f"{self.short_code}{title}"

    @property
    def level(self) -> str:
        """Human-friendly year level derived from the first digit of the course number.

        Returns the enum label or "other" when the pattern does not match a known level.
        """
        try:
            digit = int(self.number.strip()[0])  # "101" → 1
            return LEVEL_NUMBER(digit).label  # "freshman"
        except (ValueError, IndexError):  # non-digit / empty
            return "other"
        except KeyError:  # digit ∉ enum
            return "other"

    def _ensure_codes(self):
        if not self.code:
            self.code = make_course_code(self.department, number=self.number)
        if not self.short_code:
            self.short_code = make_course_code(
                self.department, number=self.number, short=True
            )

    def _ensure_dept(self):
        if not self.department_id:
            self.department = Department.get_default()

    def current_faculty(self):
        """Get the list of faculty teaching this course in the current semester."""
        Faculty = apps.get_model("people", "Faculty")

        # Returning Any from function declared to return "QuerySet[Faculty, Faculty] | None"  [no-any-return]
        # when adding the  type hint  '-> FacultyQuery | None:'
        # >TODO Try to fix this and add StudentQuery type hint to the next method too.

        semester = get_current_semester()
        if semester is None:
            return Faculty.objects.none()
        return Faculty.objects.filter(
            section__semester=semester, section__curriculum_course__course=self
        ).distinct()

    def current_students(self):
        """Returns the list of student taking this course during the current semester."""
        Student = apps.get_model("people", "Student")

        semester = get_current_semester()
        if semester is None:
            return Student.objects.none()
        return Student.objects.filter(
            student_registrations__section__semester=semester,
            student_registrations__section__curriculum_course__course=self,
        ).distinct()

    def list_curricula_str(self, sep: str = ", ") -> str:
        """Return the list of curricula including this course."""
        curricula = (
            self.in_curriculum_courses.select_related("curriculum")  # <- efficiency
            .values_list("curriculum__short_name", flat=True)  # <- this is getting the value
            .order_by("curriculum__short_name")
        )
        return sep.join(curricula)

    # ---------- hooks ----------
    def save(self, *args, **kwargs) -> None:
        """Populate code from department short_name and number before saving."""
        self._ensure_dept()
        self._ensure_codes()
        super().save(*args, **kwargs)

    @classmethod
    def for_curriculum(cls, curriculum) -> CourseQuery:
        """Return courses included in the given curriculum."""
        return cls.objects.filter(curricula=curriculum).distinct()

    @classmethod
    def get_default(cls, number: str = "0000") -> Self:
        """Return a default Course."""
        def_crs, _ = cls.objects.get_or_create(
            department=Department.get_default(),
            number=number,
            title=f"Default Course {number}",
        )
        return def_crs

    @classmethod
    def get_unique_default(cls) -> Self:
        """Return a default Course which is unique. A most 1000 course can be created."""
        number = f"{next(DEFAULT_COURSE_NO):04d}"
        return cls.get_default(number=number)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["department", "code", "number"],
                name="uniq_course_codenumber_per_department",
            ),
        ]
        ordering = ["short_code"]

# to be renamed CurriculumCourse
class CurriculumCourse(models.Model):
    """Map Curriculum instances to their constituent courses.

    It kind of a program
    Example:
        >>> CurriculumCourse.objects.create(curriculum=curriculum, course=course)

    Side Effects:
        save() defaults credit_hours to the course value when missing.
    """

    # ~~~~ Mandatory ~~~~
    # curriculum or major
    curriculum = models.ForeignKey(
        "academics.Curriculum", on_delete=models.CASCADE, related_name="programs"
    )
    course = models.ForeignKey(
        "academics.Course", on_delete=models.CASCADE, related_name="in_curriculum_courses"
    )

    # ~~~~ Auto-filled ~~~~
    is_required = models.BooleanField(default=False)  # for required general courses
    is_elective = models.BooleanField(default=False)
    history = HistoricalRecords()
    # credit hours depend on the curricula not the Course
    credit_hours = models.ForeignKey(
        "shared.CreditHour",
        on_delete=models.PROTECT,
        default=3,
        help_text="Credits to be used in this curriculum for this course",
        related_name="curriculum_courses",
    )

    def __str__(self) -> str:  # pragma: no cover
        """Return Curriculum <-> Course for readability."""
        return f"{self.course} <-> {self.curriculum}"

    def _ensure_credit_hours(self):
        """Make sure the credit_hours is set."""
        if not self.credit_hours_id:
            self.credit_hours_id = 3
        CreditHour.objects.get_or_create(
            code=self.credit_hours_id, defaults={"label": str(self.credit_hours_id)}
        )

    def save(self, *args, **kwargs):
        """Make sure we set default before saving."""
        self._ensure_credit_hours()
        super().save(*args, **kwargs)

    @classmethod
    def get_default(cls, _course: Optional[Course] = None) -> Self:
        """Returns a default CurriculumCourse."""
        def_pg, _ = cls.objects.get_or_create(
            curriculum=Curriculum.get_default(),
            course=(_course or Course.get_default()),
        )
        return def_pg

    @classmethod
    def get_unique_default(cls) -> Self:
        """Returns a default unique CurriculumCourse."""
        u_course = Course.get_unique_default()
        return cls.get_default(_course=u_course)

    def current_students(self):
        """Students enrolled in this curriculum course during the current semester."""
        Student = apps.get_model("people", "Student")
        semester = get_current_semester()
        if semester is None:
            return Student.objects.none()

        return Student.objects.filter(
            # student_registrations__section__semester=semester,
            student_registrations__section__curriculum_course=self,
        ).distinct()
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("curriculum", "course"), name="uniq_course_per_curriculum"
            )
        ]
        ordering = ["curriculum"]
        verbose_name = "Programmed Course"
        verbose_name_plural = "Programmed Courses"
