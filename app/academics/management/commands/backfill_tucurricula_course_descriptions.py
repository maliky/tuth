"""Backfill Course.description from TUCurricula import TSVs."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from django.core.management.base import BaseCommand, CommandError, CommandParser

from app.academics.course_description_backfill import backfill_course_descriptions
from app.shared.source_truth.course_aliases import DEFAULT_APPROVED_ALIAS_PATH


class Command(BaseCommand):
    """Copy safe TUCurricula descriptions onto existing Course rows."""

    help = (
        "Backfill blank Course.description fields from data/tucurricula_import. "
        "Dry-run by default; pass --apply to write database changes."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        """Register command options."""
        parser.add_argument(
            "--import-dir",
            default="data/tucurricula_import",
            help="Directory containing org-derived academic_course.tsv.",
        )
        parser.add_argument(
            "--approved-aliases",
            default=str(DEFAULT_APPROVED_ALIAS_PATH),
            help="TSV of approved source->target course aliases.",
        )
        parser.add_argument(
            "--report-path",
            default=None,
            help="Audit TSV path. Defaults to logs/tucurricula_description_backfill.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write safe description updates. Omit for dry-run.",
        )
        parser.add_argument(
            "--overwrite-existing",
            action="store_true",
            help="Replace existing descriptions. Default only fills blanks.",
        )

    def handle(self, *args: object, **options: object) -> None:
        """Run description backfill and write an audit report."""
        import_dir = Path(cast(str, options["import_dir"])).expanduser()
        approved_aliases = Path(cast(str, options["approved_aliases"])).expanduser()
        report_path = _report_path(cast(str | None, options.get("report_path")))
        apply = bool(options.get("apply"))
        overwrite_existing = bool(options.get("overwrite_existing"))

        _validate_inputs(import_dir, approved_aliases)
        summary = backfill_course_descriptions(
            import_dir=import_dir,
            approved_aliases_path=approved_aliases,
            report_path=report_path,
            apply=apply,
            overwrite_existing=overwrite_existing,
        )
        mode = "applied" if apply else "dry-run"
        self.stdout.write(self.style.SUCCESS(f"Course description backfill {mode}."))
        self.stdout.write(f"considered: {summary.considered}")
        self.stdout.write(f"updated: {summary.updated}")
        self.stdout.write(f"would_update: {summary.would_update}")
        self.stdout.write(f"skipped_existing: {summary.skipped_existing}")
        self.stdout.write(f"skipped_no_match: {summary.skipped_no_match}")
        self.stdout.write(f"skipped_ambiguous: {summary.skipped_ambiguous}")
        self.stdout.write(f"report_path: {summary.report_path}")


def _report_path(raw_report_path: str | None) -> Path:
    """Return explicit report path or timestamped ignored logs path."""
    if raw_report_path:
        return Path(raw_report_path).expanduser()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("logs") / "tucurricula_description_backfill" / f"{stamp}.tsv"


def _validate_inputs(import_dir: Path, approved_aliases: Path) -> None:
    """Raise CommandError for missing command inputs."""
    course_path = import_dir / "academic_course.tsv"
    if not course_path.exists():
        raise CommandError(f"Missing TUCurricula course TSV: {course_path}")
    if not approved_aliases.exists():
        raise CommandError(f"Missing approved aliases TSV: {approved_aliases}")
