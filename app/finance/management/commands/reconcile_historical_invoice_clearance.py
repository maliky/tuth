"""Clear historical open semester invoices with auditable payment rows."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandParser

from app.finance.historical_clearance import (
    DEFAULT_CUTOFF_SEMESTER,
    reconcile_historical_clearance,
)


class Command(BaseCommand):
    """Reconcile historical parent invoices by recording cleared payments."""

    help = (
        "Create or update cleared payment rows for open historical semester invoices. "
        "Dry-run is the default; pass --apply to mutate data."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        """Register command options."""
        parser.add_argument(
            "--cutoff-semester",
            default=DEFAULT_CUTOFF_SEMESTER,
            help="Current semester boundary, e.g. 25-26-S3. Earlier semesters clear.",
        )
        parser.add_argument(
            "--student",
            default="",
            help="Optional student username, student_id, or database id.",
        )
        parser.add_argument(
            "--log-path",
            default="",
            help="Optional CSV audit path. Defaults under logs/finance_reconciliation.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually create/update cleared payment rows.",
        )

    def handle(self, *args: object, **options: object) -> None:
        """Run the historical clearance reconciliation."""
        result = reconcile_historical_clearance(
            cutoff_semester_code=str(options["cutoff_semester"]),
            student_token=str(options["student"]),
            raw_log_path=str(options["log_path"]),
            apply_changes=bool(options["apply"]),
        )
        self.stdout.write(self.style.SUCCESS(result.summary()))


__all__ = ["Command"]
