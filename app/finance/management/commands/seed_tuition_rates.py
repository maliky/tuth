"""Seed model-backed tuition rates from existing semester policy."""

from __future__ import annotations

from decimal import Decimal
from typing import cast

from django.core.management.base import BaseCommand, CommandParser

from app.academics.choices import AcademicCareer
from app.finance.course_fee_policy import tuition_rate_for_semester
from app.finance.models.tuition import TuitionRate
from app.timetable.models.semester import Semester


class Command(BaseCommand):
    """Create tuition-rate rows for undergraduate and graduate careers."""

    help = "Seed semester/career tuition rates without changing invoices."

    def add_arguments(self, parser: CommandParser) -> None:
        """Register command options."""
        parser.add_argument(
            "--semester",
            action="append",
            help="Semester code like 25-26_Sem3. Repeatable. Defaults to all.",
        )
        parser.add_argument(
            "--graduate-rate",
            default="50.00",
            help="Graduate tuition per credit. Defaults to 50.00.",
        )
        parser.add_argument("--apply", action="store_true", help="Persist changes.")

    def handle(self, *args: object, **options: object) -> None:
        """Seed missing tuition-rate rows."""
        semester_codes = list(cast(list[str], options.get("semester") or []))
        semesters = _semester_queryset(semester_codes)
        graduate_rate = Decimal(str(options["graduate_rate"]))
        apply_changes = bool(options.get("apply"))
        created = 0
        existing = 0
        for semester in semesters:
            undergrad_rate = tuition_rate_for_semester(
                semester,
                academic_career=AcademicCareer.UNDERGRADUATE,
            )
            for career, rate, source in (
                (
                    AcademicCareer.UNDERGRADUATE,
                    undergrad_rate,
                    "legacy tuition_rates.tsv",
                ),
                (AcademicCareer.GRADUATE, graduate_rate, "graduate default"),
            ):
                if TuitionRate.objects.filter(
                    semester=semester,
                    academic_career=career,
                ).exists():
                    existing += 1
                    continue
                created += 1
                if apply_changes:
                    TuitionRate.objects.create(
                        semester=semester,
                        academic_career=career,
                        tuition_per_credit=rate,
                        foreigner_tuition_per_credit=rate,
                        source=source,
                    )
        mode = "applied" if apply_changes else "dry-run"
        self.stdout.write(
            self.style.SUCCESS(
                f"tuition seed {mode}: created={created} existing={existing}"
            )
        )


def _semester_queryset(codes: list[str]):
    """Return semesters matching code arguments or every configured semester."""
    qs = Semester.objects.select_related("academic_year").order_by(
        "academic_year__start_date",
        "number",
    )
    if not codes:
        return list(qs)
    selected = []
    for code in codes:
        normalized = _norm_sem_code(code)
        for semester in qs:
            sem_code = _norm_sem_code(f"{semester.academic_year.code}-S{semester.number}")
            alt_code = _norm_sem_code(str(semester))
            if normalized in {sem_code, alt_code}:
                selected.append(semester)
                break
    return selected


def _norm_sem_code(value: str) -> str:
    """Normalize common semester-code spellings for CLI matching."""
    return (
        value.strip()
        .lower()
        .replace("/", "-")
        .replace("_sem", "-s")
        .replace("sem", "s")
        .replace("_", "-")
    )
