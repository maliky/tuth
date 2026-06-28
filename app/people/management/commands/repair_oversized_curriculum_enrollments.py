"""Repair student primary enrollments attached to oversized curricula."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandParser

from app.people.services.curriculum_repair import (
    DEFAULT_MAX_CREDITS,
    repair_oversized_curriculum_enrollments,
)


class Command(BaseCommand):
    """Run auditable oversized-curriculum enrollment repair."""

    help = (
        "Move students whose primary curriculum exceeds the credit ceiling to a "
        "deterministic approved active curriculum. Dry-run is the default."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        """Register command options."""
        parser.add_argument(
            "--max-credits",
            type=int,
            default=DEFAULT_MAX_CREDITS,
            help="Credit total above which a curriculum is treated as oversized.",
        )
        parser.add_argument(
            "--student",
            default="",
            help="Optional student username, student_id, or database id.",
        )
        parser.add_argument(
            "--log-path",
            default="",
            help="Optional CSV audit path. Defaults under logs/curriculum_reconciliation.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually move deterministic primary curriculum enrollments.",
        )

    def handle(self, *args: object, **options: object) -> None:
        """Run the repair command."""
        result = repair_oversized_curriculum_enrollments(
            max_credits=int(str(options["max_credits"])),
            student_token=str(options["student"]),
            raw_log_path=str(options["log_path"]),
            apply_changes=bool(options["apply"]),
        )
        self.stdout.write(self.style.SUCCESS(result.summary()))


__all__ = ["Command"]
