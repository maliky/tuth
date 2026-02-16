"""Semester module."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional, Self, TypeAlias

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
from simple_history.models import HistoricalRecords

from app.shared.mixins import SimpleTableMixin, StatusableMixin
from app.shared.types import OpenRegistrationSemesterResultT
from app.timetable.choices import SEMESTER_NUMBER
from app.timetable.models.academic_year import AcademicYear
from app.timetable.utils import validate_subperiod

SemesterDateDefaultsT: TypeAlias = tuple[date, date]


def _academic_year_end_date(academic_year: AcademicYear) -> date:
    """Return the academic year end date, computing it if missing."""
    if academic_year.end_date:
        return academic_year.end_date
    return academic_year.start_date.replace(year=academic_year.start_date.year + 1) - (
        timedelta(days=1)
    )


def _dft_sem_dates(academic_year: AcademicYear, number: int) -> SemesterDateDefaultsT:
    """Return default semester start/end dates per academic year rules."""
    start_year = academic_year.start_date.year
    end_year = start_year + 1
    academic_year_end = _academic_year_end_date(academic_year)
    if number == 0:
        return academic_year.start_date, academic_year_end
    if number == SEMESTER_NUMBER.FIRST:
        return academic_year.start_date, date(start_year, 12, 31)
    if number == SEMESTER_NUMBER.SECOND:
        return date(end_year, 1, 1), date(end_year, 5, 31)
    if number == SEMESTER_NUMBER.VACATION:
        return date(end_year, 6, 1), academic_year_end
    return academic_year.start_date, academic_year_end


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
    end_date = models.DateField(null=True, blank=True)
    # Free-form notes for admin tracking.
    info = models.TextField(blank=True, default="")

    # > this is not clear. Why do we need that ? why a set ? or dict ?
    REGISTRATION_OPEN_CODES = "registration"

    def _ensure_dft_dates(self) -> None:
        """Ensure default dates are applied when missing."""
        if not self.academic_year_id:
            return
        default_start, default_end = _dft_sem_dates(self.academic_year, int(self.number))
        if not self.start_date:
            self.start_date = default_start
        if not self.end_date:
            self.end_date = default_end

    def clean(self) -> None:
        """Ensure semester dates stay within the academic year boundaries."""
        # Default semester dates based on the academic year rules.
        self._ensure_dft_dates()

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
            # Use a non-field error so admin list edits can render the message.
            label="__all__",
        )
        self.validate_status(SemesterStatus.objects.all())

    def _ensure_status(self):
        SemesterStatus._populate_attributes_and_db()
        if not self.status_id:
            self.status_id = "planning"

    def save(self, *args, **kwargs):
        # Ensure default date ranges are always set, even outside form validation.
        self._ensure_dft_dates()
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
    def get_current_semester(cls) -> "Semester":
        """Return the latest semester whose start date is on or before today."""
        today = timezone.now().date()
        return cls.get_default(today)

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

        # Here it would be good to take the semster of the year with the start  date
        # or do a test on start date with default semster start dates
        ay = AcademicYear.get_default(ref_date)

        # Ensure statuses are present before creating a semester.
        SemesterStatus._populate_attributes_and_db()
        sem1_start, sem1_end = _dft_sem_dates(ay, SEMESTER_NUMBER.FIRST)

        # Avoid duplicate semesters when the academic year already has Sem 1.
        semester, _created = cls.objects.get_or_create(
            academic_year=ay,
            number=SEMESTER_NUMBER.FIRST,
            defaults={"start_date": sem1_start, "end_date": sem1_end},
        )
        return semester

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
