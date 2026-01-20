"""Semester module."""

from __future__ import annotations

from datetime import date
from typing import Optional

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
from simple_history.models import HistoricalRecords

from app.shared.types import OpenRegistrationSemesterResultT
from app.shared.mixins import SimpleTableMixin
from app.shared.status.mixins import StatusableMixin
from app.timetable.choices import SEMESTER_NUMBER
from app.timetable.models.academic_year import AcademicYear
from app.timetable.utils import validate_subperiod


class Semester(StatusableMixin, models.Model):
    """Major section of academic year (e.g. semester 1, 2 or 3 vacations).

    Example:
        >>> Semester.objects.create(academic_year=year, number=1)
    """

    # ~~~~~~~~ Mandatory ~~~~~~~~
    academic_year = models.ForeignKey("timetable.AcademicYear", on_delete=models.PROTECT)
    number = models.PositiveSmallIntegerField(
        choices=SEMESTER_NUMBER.choices, help_text="Semester number"
    )
    status = models.ForeignKey(
        "timetable.SemesterStatus",
        on_delete=models.PROTECT,
        related_name="semesters",
        default="planning",
    )

    # ~~~~ Auto-filled ~~~~
    history = HistoricalRecords()
    start_date = models.DateField(null=True, blank=True)

    # ~~~~~~~~ Optional ~~~~~~~~
    # Could set this to academic_year.start_date automatically on save
    # and force non-null values.
    end_date = models.DateField(null=True, blank=True)
    # Free-form notes for admin tracking.
    info = models.TextField(blank=True, default="")

    # > this is not clear. Why do we need that ? why a set ? or dict ?
    REGISTRATION_OPEN_CODES = "registration"

    def clean(self) -> None:
        """Ensure semester dates stay within the academic year boundaries."""
        if not self.start_date:
            self.start_date = self.academic_year.start_date

        # Semester.clean() and Term.clean() call validate_subperiod() but not
        # full_clean() on related objects. In admin workflows the parent may still
        # carry invalid dates. Consider a parent-before-child save order or
        # database-level CHECK constraints.
        validate_subperiod(
            sub_start=self.start_date,
            sub_end=self.end_date,
            container_start=self.academic_year.start_date,
            container_end=self.academic_year.end_date,
            overlap_qs=Semester.objects.filter(academic_year=self.academic_year).exclude(
                pk=self.pk
            ),
            overlap_message="Overlapping Semesters in the same academic year.",
            label="semester",
        )
        self.validate_status(SemesterStatus.objects.all())

    def _ensure_status(self):
        SemesterStatus._populate_attributes_and_db()
        if not self.status_id:
            self.status_id = "planning"

    def save(self, *args, **kwargs):
        self._ensure_status()
        return super().save(*args, **kwargs)

    def is_registration_open(self) -> bool:
        """Return True when the semester is open for course selection."""
        return self.status_id == self.REGISTRATION_OPEN_CODES

    @classmethod
    def registration_open_semester(cls) -> OpenRegistrationSemesterResultT:
        """Return the open registration semester, with error msg if more than one exists."""
        open_qs = cls.objects.filter(status_id=cls.REGISTRATION_OPEN_CODES)
        if open_qs.count() > 1:
            return None, "Multiple semesters are open for registration."
        return open_qs.first(), None

    @classmethod
    def get_default(cls, today: date | None = None) -> "Semester":
        """Return the current semester or create one for the current academic year."""
        ref_date = today or timezone.now().date()
        semester = (
            cls.objects.filter(start_date__lte=ref_date)
            .filter(Q(end_date__gte=ref_date) | Q(end_date__isnull=True))
            .order_by("-start_date")
            .first()
        )
        if semester:
            return semester
        academic_year = AcademicYear.get_default(ref_date)
        fallback = (
            cls.objects.filter(academic_year=academic_year).order_by("number").first()
        )
        if fallback:
            return fallback
        # Ensure statuses are present before creating a semester.
        SemesterStatus._populate_attributes_and_db()
        return cls.objects.create(
            academic_year=academic_year,
            number=SEMESTER_NUMBER.FIRST,
            start_date=academic_year.start_date,
            end_date=academic_year.end_date,
        )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["academic_year", "number"], name="uniq_semester_per_year"
            ),
            # I will need to take care of this migration online also
            models.UniqueConstraint(
                fields=["status"],
                condition=models.Q(status_id="registration"),
                name="uniq_open_registration_semester",
            ),
        ]
        ordering = ["start_date"]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.academic_year.code}_Sem{self.number}"


class SemesterStatus(SimpleTableMixin):
    """Track the lifecycle of a semester (planning, registration, locked)."""

    DEFAULT_VALUES = [
        ("planning", "Planning"),
        ("registration", "Registration Open"),
        ("running", "Registration Closed, Semester running"),
        ("locked", "Registration Closed, Semester locked"),
    ]

    class Meta:
        verbose_name = "Semester Status"
        verbose_name_plural = "Semester Statuses"
