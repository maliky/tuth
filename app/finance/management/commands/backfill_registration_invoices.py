"""Backfill course invoices for imported registrations."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db.models import Q

from app.finance.course_fee_policy import unresolved_lab_fee_candidate_rows
from app.finance.registration_invoices import (
    invoice_generation_registration_qs,
    invoiceable_registration_qs,
    materialize_registration_invoices,
)
from app.people.models.student import Student
from app.registry.models.registration import Registration
from app.timetable.models.semester import Semester
from app.timetable.utils import normalize_academic_year


class Command(BaseCommand):
    """Create finance invoice rows for invoiceable registrations."""

    help = (
        "Backfill missing CrsInvoice rows from pending/partially cleared registrations."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        """Register command options."""
        parser.add_argument(
            "--student",
            default="",
            help="Limit to one student by username, student_id, or database id.",
        )
        parser.add_argument(
            "--semester-id",
            type=int,
            default=None,
            help="Limit to one semester database id.",
        )
        parser.add_argument(
            "--academic-year",
            default="",
            help="Limit to an academic year code such as 25-26 or 2025/2026.",
        )
        parser.add_argument(
            "--semester-number",
            type=int,
            default=None,
            help="Limit to a semester number within --academic-year.",
        )
        parser.add_argument(
            "--include-existing",
            action="store_true",
            help="Patch stale existing invoice rows as well as missing rows.",
        )
        parser.add_argument(
            "--write-lab-report",
            default="",
            help="Optional TSV path for non-general 4-credit courses needing lab fees.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be created without writing invoices.",
        )

    def handle(self, *args: object, **options: object) -> None:
        """Run the registration invoice backfill."""
        student_token = str(options.get("student", "")).strip()
        semester_id = _resolve_semester_id(
            semester_id=options.get("semester_id"),
            academic_year=str(options.get("academic_year", "")).strip(),
            semester_number=options.get("semester_number"),
        )
        include_existing = bool(options.get("include_existing"))
        lab_report_path = str(options.get("write_lab_report", "")).strip()
        dry_run = bool(options.get("dry_run"))
        student_id = _resolve_student_id(student_token) if student_token else None
        if include_existing:
            registrations = invoiceable_registration_qs(
                student_id=student_id,
                semester_id=semester_id,
                missing_only=False,
            )
        else:
            registrations = invoice_generation_registration_qs(
                student_id=student_id,
                semester_id=semester_id,
            )
        registration_count = registrations.count()
        if lab_report_path:
            _write_lab_report(Path(lab_report_path), registrations)
        summary = materialize_registration_invoices(registrations, dry_run=dry_run)
        action = "would process" if dry_run else "processed"
        self.stdout.write(
            self.style.SUCCESS(
                f"Registration invoice backfill {action} {registration_count} "
                f"registration(s): {summary['created']} created, "
                f"{summary['updated']} updated, {summary['existing']} existing, "
                f"{summary['skipped_zero']} zero-amount skipped."
            )
        )


def _resolve_student_id(token: str) -> int:
    """Resolve a student selector to a database id."""
    query = Q(user__username=token) | Q(username=token) | Q(student_id=token)
    if token.isdigit():
        query |= Q(id=int(token))
    student = Student.objects.filter(query).order_by("id").first()
    if student is None:
        raise CommandError(f"Student not found: {token}")
    return int(student.id)


def _resolve_semester_id(
    *,
    semester_id: object,
    academic_year: str,
    semester_number: object,
) -> int | None:
    """Resolve direct or academic-year/semester-number filters."""
    if isinstance(semester_id, int):
        return semester_id
    if not academic_year and semester_number is None:
        return None
    if not academic_year or not isinstance(semester_number, int):
        raise CommandError("--academic-year and --semester-number must be used together.")
    year_code = normalize_academic_year(academic_year)
    semester = Semester.objects.filter(
        academic_year__code=year_code,
        number=semester_number,
    ).first()
    if semester is None:
        raise CommandError(f"Semester not found: {year_code} Sem{semester_number}")
    return int(semester.id)


def _write_lab_report(path: Path, registrations: Iterable[Registration]) -> None:
    """Write likely lab-fee candidates before materializing invoices."""
    rows = unresolved_lab_fee_candidate_rows(registrations)
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = [
        "course_key",
        "course_code",
        "course_title",
        "credit_hours",
        "computed_amount",
        "registration_count",
        "reason",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


__all__ = ["Command"]
