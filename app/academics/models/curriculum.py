"""Curriculum module."""

from __future__ import annotations
from django.db.models import Count

from django.apps import apps
from datetime import date
from typing import Self

from app.shared.mixins import SimpleTableMixin
from app.shared.utils import as_title
from django.db import models
from simple_history.models import HistoricalRecords
from app.academics.models.college import College
from app.shared.status.mixins import StatusableMixin


class CurriculumStatus(SimpleTableMixin):
    """Code/label pairs for curriculum validation status."""

    DEFAULT_VALUES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("needs_revision", "Needs Revision"),
    ]

    class Meta:
        verbose_name = "Curriculum Status"
        verbose_name_plural = "Curriculum Status"


# need to update the docs
class Curriculum(StatusableMixin, models.Model):
    """Set of courses that make up a degree Curriculum/program within a college.

    Example:
        >>> col = College.objects.create(code="COAS", long_name="Arts and Sciences")
        >>> Curriculum.objects.create(short_name="BSCS", college=col)

    We use a default curriculum encompassing all curriculum_courses when none is specified;
    otherwise the student is limited to the courses listed in their curriculum.

    Concerning credit hours, usualy between 120-128 (GE 30-40, Major/Specific 30-60, Minor/elective (rest))
    """

    # ~~~~~~~~ Mandatory ~~~~~~~~
    short_name = models.CharField(max_length=40)

    # ~~~~ Auto-filled ~~~~
    college = models.ForeignKey(
        "academics.College", on_delete=models.CASCADE, related_name="curricula"
    )
    creation_date = models.DateField(default=date.today)
    is_active = models.BooleanField(default=False)

    status = models.ForeignKey(
        "academics.CurriculumStatus",
        on_delete=models.PROTECT,
        default="pending",
        related_name="curricula",
        verbose_name="Validation Status",
    )
    history = HistoricalRecords()

    # ~~~~~~~~ Optional ~~~~~~~~
    long_name = models.CharField(max_length=255, blank=True, null=True)
    # this is a shortcut from curriculum <- curriculum_courses . course
    # The idea is to have a catalogue C of curriculum course been authorative
    # the list of curriculum_courses.course should be included in C.
    # can a course be not offered  in any curricula ?
    # needs clarification...
    curriculum_course = models.ManyToManyField(
        "academics.Course",
        through="academics.CurriculumCourse",
        related_name="curricula",  # <-- reverse accessor course.curricula
        blank=True,
    )

    def __str__(self) -> str:  # pragma: no cover
        """Return the college (if set): & curriculum short name."""
        _prefix = f"({self.college}) " if self.college_id else ""
        return _prefix + self.short_name 

    @classmethod
    def get_default(cls, short_name="DFT_CUR") -> Self:
        """Returns a default curriculum."""
        def_curriculum, _ = cls.objects.get_or_create(
            short_name=short_name,
            long_name="Default Curriculum",
            college=College.get_default(),
        )
        return def_curriculum

    def _ensure_activity(self):
        """Make sure than only an aproved curriculum can be active."""
        # > TODO would be good to bubble up a warning message to inform user
        # of the change.
        if self.status_id != "approved":
            self.is_active = False

    def _ensure_status(self):
        """Make sure the curriculum has a status set."""
        if not self.status_id:
            # >? given that id is no different from code is it necessary to use _id ? oui si on veux pas
            # faire self.status.code
            self.status_id = "pending"
        # just to make sure it is created.
        CurriculumStatus.objects.get_or_create(
            code=self.status_id,
            defaults={"label": as_title(self.status_id)},
        )

    def course_count(self):
        """Count hown many courses attached to this curriculum."""
        return self.curriculum_course.count()

    def student_count(self):
        """Count the number of student who selected this curriculum."""
        return self.students.count()
    def current_student_count(self):
        """Total number of students currently enrolled in courses of this curriculum."""
        Student = apps.get_model("people", "Student")
        return (
            Student.objects.filter(
                student_registrations__section__curriculum_course__curriculum=self,
            )
            .distinct()
            .count()
        )    
    def save(self, *args, **kwargs):
        """Save a curriculum instance while setting defaults."""
        if not self.college_id:
            self.college = College.get_default()
        self._ensure_status()
        self._ensure_activity()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        """Validate the curriculum and its current status."""
        super().clean()
        self.validate_status(CurriculumStatus.objects.all())

    class Meta:
        ordering = ["college", "short_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["college", "short_name"],
                condition=models.Q(is_active=True),
                name="uniq_active_curriculum_college",
            )
        ]
