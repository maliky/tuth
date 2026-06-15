"""Backfill global prerequisite edges from TUCurricula import TSVs."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from django.core.management.base import BaseCommand, CommandError, CommandParser

from app.academics.course_prerequisite_backfill import backfill_global_prerequisites


class Command(BaseCommand):
    """Copy prereq_all facts into global Course prerequisite edges."""

    help = (
        "Backfill curriculum-independent Prerequisite rows from "
        "TUCurricula academic_curriculum_requirement.tsv. Dry-run by default."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        """Register command options."""
        parser.add_argument(
            "--import-dir",
            default="data/tucurricula_import",
            help="Directory containing TUCurricula academic_course and requirement TSVs.",
        )
        parser.add_argument(
            "--report-path",
            default=None,
            help="Audit TSV path. Defaults to logs/tucurricula_prereq_backfill.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write global prerequisite edges. Omit for dry-run.",
        )

    def handle(self, *args: object, **options: object) -> None:
        """Run the prerequisite backfill and print summary counts."""
        import_dir = Path(cast(str, options["import_dir"])).expanduser()
        report_path = _report_path(cast(str | None, options.get("report_path")))
        apply = bool(options.get("apply"))
        _validate_inputs(import_dir)
        summary = backfill_global_prerequisites(
            import_dir=import_dir,
            report_path=report_path,
            apply=apply,
        )
        mode = "applied" if apply else "dry-run"
        self.stdout.write(self.style.SUCCESS(f"Global prerequisite backfill {mode}."))
        self.stdout.write(f"source_pairs: {summary.source_pairs}")
        self.stdout.write(f"created: {summary.created}")
        self.stdout.write(f"would_create: {summary.would_create}")
        self.stdout.write(f"skipped_existing: {summary.skipped_existing}")
        self.stdout.write(
            f"skipped_unresolved_target: {summary.skipped_unresolved_target}"
        )
        self.stdout.write(
            f"skipped_unresolved_required: {summary.skipped_unresolved_required}"
        )
        self.stdout.write(f"skipped_self: {summary.skipped_self}")
        self.stdout.write(f"report_path: {summary.report_path}")


def _report_path(raw_report_path: str | None) -> Path:
    """Return explicit report path or timestamped ignored logs path."""
    if raw_report_path:
        return Path(raw_report_path).expanduser()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("logs") / "tucurricula_prereq_backfill" / f"{stamp}.tsv"


def _validate_inputs(import_dir: Path) -> None:
    """Raise CommandError for missing import files."""
    required = ("academic_course.tsv", "academic_curriculum_requirement.tsv")
    missing = [name for name in required if not (import_dir / name).exists()]
    if missing:
        raise CommandError(f"Missing TUCurricula TSVs: {', '.join(missing)}")
