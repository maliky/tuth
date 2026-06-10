"""Backfill course invoices for imported registrations."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db.models import Q

from app.finance.registration_invoices import (
    invoiceable_registration_qs,
    materialize_registration_invoices,
)
from app.people.models.student import Student


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
            "--dry-run",
            action="store_true",
            help="Report what would be created without writing invoices.",
        )

    def handle(self, *args: object, **options: object) -> None:
        """Run the registration invoice backfill."""
        student_token = str(options.get("student", "")).strip()
        semester_id = options.get("semester_id")
        dry_run = bool(options.get("dry_run"))
        student_id = _resolve_student_id(student_token) if student_token else None
        registrations = invoiceable_registration_qs(
            student_id=student_id,
            semester_id=semester_id if isinstance(semester_id, int) else None,
            missing_only=True,
        )
        registration_count = registrations.count()
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


__all__ = ["Command"]
