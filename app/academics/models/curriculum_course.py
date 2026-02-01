"""Course module."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional, Self, TypeAlias, cast

from django.db import models
from simple_history.models import HistoricalRecords

from app.academics.choices import LEVEL_NUMBER
from app.academics.models.course import Course
from app.academics.models.curriculum import Curriculum
from app.finance.models.course_fee import CourseFee, CurriculumCourseFee
from app.registry.models import CreditHour
from app.shared.types import FacultyQuery, StudentQuery
from app.timetable.choices import SEMESTER_NUMBER
from app.timetable.models.semester import Semester


TUITION_RATE_PER_CREDIT = Decimal("5.00")
ChoiceListT: TypeAlias = list[tuple[int, str]]


def _semester_number_choices() -> ChoiceListT:
    """Return semester choices including an undefined value."""
    choices = [(0, "Undefined (0)")]
    choices.extend(list(SEMESTER_NUMBER.choices))
    return choices


def _year_number_choices() -> ChoiceListT:
    """Return year level choices mapped to student levels."""
    choices: ChoiceListT = [(int(LEVEL_NUMBER.UNDEF.value), "Undefined (99)")]
    label_overrides = {
        LEVEL_NUMBER.FOUR: "Senior 1",
        LEVEL_NUMBER.FIVE: "Senior 2",
    }
    for level in (
        LEVEL_NUMBER.ONE,
        LEVEL_NUMBER.TWO,
        LEVEL_NUMBER.THREE,
        LEVEL_NUMBER.FOUR,
        LEVEL_NUMBER.FIVE,
    ):
        label = label_overrides.get(level, level.label.title())
        choices.append((int(level.value), label))
    return choices


SEMESTER_NUMBER_CHOICES = tuple(_semester_number_choices())
YEAR_NUMBER_CHOICES = tuple(_year_number_choices())
LEVEL_NUMBER_CHOICES = tuple(
    [(int(LEVEL_NUMBER.UNDEF.value), "Undefined (99)"), (0, "Remedial (0)")]
    + [
        (
            level,
            f"Level {level} (Y{(level - 1) // 2 + 1}S{1 if level % 2 else 2})",
        )
        for level in range(1, 11)
    ]
)


class CurriculumCourse(models.Model):
    """Map Curriculum instances to their constituent courses.

    It can be called a 'program'
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
        "registry.CreditHour",
        on_delete=models.PROTECT,
        default=3,
        help_text="Credits to be used in this curriculum for this course",
        related_name="curriculum_courses",
    )
    semester_number = models.PositiveSmallIntegerField(
        choices=SEMESTER_NUMBER_CHOICES,
        default=0,
        db_index=True,
        help_text="Normal semester number for this course in the curriculum",
    )
    level_number = models.PositiveSmallIntegerField(
        choices=LEVEL_NUMBER_CHOICES,
        default=LEVEL_NUMBER.UNDEF,
        null=True,
        blank=True,
        db_index=True,
        help_text="Derived level number (0=remedial, 1-10=Y1S1..Y5S2, 99=undefined)",
    )
    year_number = models.PositiveSmallIntegerField(
        choices=YEAR_NUMBER_CHOICES,
        default=LEVEL_NUMBER.UNDEF,
        db_index=True,
        help_text="Normal year level for this course in the curriculum",
    )
    required_group_number = models.PositiveSmallIntegerField(
        default=0,
        db_index=True,
        help_text="Group number for required elective selection (0 = none)",
    )

    @classmethod
    def get_default(cls, _course: Optional[Course] = None) -> Self:
        """Returns a default CurriculumCourse."""
        def_pg, _ = cls.objects.get_or_create(
            curriculum=Curriculum.get_default(),
            course=(_course or Course.get_default()),
        )
        return cast(Self, def_pg)

    @classmethod
    def get_unique_default(cls) -> Self:
        """Returns a default unique CurriculumCourse."""
        u_course = Course.get_unique_default()
        return cls.get_default(_course=u_course)

    def __str__(self) -> str:  # pragma: no cover
        """Return Curriculum <-> Course for readability."""
        return f"{self.course} :: {self.curriculum}"

    def _ensure_credit_hours(self):
        """Make sure the credit_hours is set."""
        if not self.credit_hours_id:
            self.credit_hours_id = 3
        CreditHour.objects.get_or_create(
            code=self.credit_hours_id, defaults={"label": str(self.credit_hours_id)}
        )

    def _ensure_year_semester_from_level(self) -> None:
        """Autofill year/semester when a level number is provided."""
        level_value_raw = getattr(self, "level_number", None)
        if level_value_raw is None:
            return
        level_value = int(level_value_raw)
        if level_value == int(LEVEL_NUMBER.UNDEF.value):
            return
        if level_value <= 0:
            self.year_number = LEVEL_NUMBER.UNDEF
            self.semester_number = 0
            return
        if 1 <= level_value <= 10:
            year_value = (level_value - 1) // 2 + 1
            semester_value = 1 if level_value % 2 else 2
            self.year_number = year_value
            self.semester_number = semester_value
            return

    def current_faculty(self) -> FacultyQuery:
        """Get the list of faculty teaching this course in the current semester."""
        from app.people.models.faculty import Faculty

        semester = Semester.get_current_semester()
        faculty_qs = Faculty.objects.filter(
            section__semester=semester, section__curriculum_course=self
        ).distinct()
        return faculty_qs

    def current_students(self) -> StudentQuery:
        """Students enrolled in this curriculum course during the current semester."""
        from app.people.models.student import Student

        semester = Semester.get_current_semester()
        students_qs = Student.objects.filter(
            student_registrations__section__semester=semester,
            student_registrations__section__curriculum_course=self,
        ).distinct()
        return students_qs

    def tuition_for(self) -> Decimal:
        """Return the tuition amount for this curriculum course."""
        credit_hours = getattr(self, "credit_hours", None)
        credit_code = getattr(credit_hours, "code", None)
        return Decimal(int(credit_code or 0)) * TUITION_RATE_PER_CREDIT

    def total_fee(self, semester) -> Decimal:
        """Return tuition plus resolved additional fees for a semester."""
        curriculum_semester_fees = (
            CurriculumCourseFee.objects.filter(curriculum_course=self, semester=semester)
            if semester
            else CurriculumCourseFee.objects.none()
        )
        curriculum_default_fees = CurriculumCourseFee.objects.filter(
            curriculum_course=self, semester__isnull=True
        )
        course_semester_fees = (
            CourseFee.objects.filter(course=self.course, semester=semester)
            if semester
            else CourseFee.objects.none()
        )
        course_default_fees = CourseFee.objects.filter(
            course=self.course, semester__isnull=True
        )

        def _fee_map(fees):
            return {fee.fee_type_id: fee.amount for fee in fees}

        curriculum_semester_map = _fee_map(curriculum_semester_fees)
        curriculum_default_map = _fee_map(curriculum_default_fees)
        course_semester_map = _fee_map(course_semester_fees)
        course_default_map = _fee_map(course_default_fees)

        fee_types = set()
        fee_types.update(curriculum_semester_map)
        fee_types.update(curriculum_default_map)
        fee_types.update(course_semester_map)
        fee_types.update(course_default_map)

        fee_total = Decimal("0.00")
        for fee_type_id in fee_types:
            if fee_type_id in curriculum_semester_map:
                fee_total += curriculum_semester_map[fee_type_id]
            elif fee_type_id in curriculum_default_map:
                fee_total += curriculum_default_map[fee_type_id]
            elif fee_type_id in course_semester_map:
                fee_total += course_semester_map[fee_type_id]
            elif fee_type_id in course_default_map:
                fee_total += course_default_map[fee_type_id]

        return self.tuition_for() + fee_total

    def save(self, *args, **kwargs):
        """Make sure we set default before saving."""
        self._ensure_credit_hours()
        self._ensure_year_semester_from_level()
        super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("curriculum", "course"), name="uniq_course_per_curriculum"
            )
        ]
        ordering = ["curriculum"]
        verbose_name = "Programmed Course"
        verbose_name_plural = "Programmed Courses"
