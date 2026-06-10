"""Build a read-only comprehensive TUSIS source/pseudo-truth bundle."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from django.core.management.base import BaseCommand, CommandParser

from app.shared.source_truth.builder import (
    TruthBuildConfigT,
    build_tusis_truth,
    default_output_dir,
)


class Command(BaseCommand):
    """Generate reconciliation SQLite/TSV outputs without mutating Django data."""

    help = "Build source-truth SQLite and TSV reports from SmartSchool, GradPro, and TUCurricula."

    def add_arguments(self, parser: CommandParser) -> None:
        """Register source and output path options."""
        parser.add_argument(
            "--smartschool-dir",
            default="Seed_data/SmartSchoolDB_20260609",
            help="Latest SmartSchool CSV export directory.",
        )
        parser.add_argument(
            "--smartschool-fallback-dir",
            default="Seed_data/Fundamentals",
            help="Older import-ready SmartSchool fallback directory.",
        )
        parser.add_argument(
            "--grapro-csv-dir",
            default="Seed_data/Archives/DBs/GP_DB250717",
            help="GradPro legacy CSV export directory.",
        )
        parser.add_argument(
            "--grapro-mdb",
            default="Seed_data/Archives/DBs/grapro-backup-20250717-154832.mdb",
            help="GradPro Access MDB backup for table inventory.",
        )
        parser.add_argument(
            "--tucurricula-import-dir",
            default="data/tucurricula_import",
            help="Pre-extracted TUCurricula import TSV directory.",
        )
        parser.add_argument(
            "--output-dir",
            default=None,
            help="Output directory. Defaults to logs/tusis_truth/<UTC timestamp>.",
        )

    def handle(self, *args: object, **options: object) -> None:
        """Run the read-only source-truth build."""
        output_option = cast(str | None, options.get("output_dir"))
        config = TruthBuildConfigT(
            smartschool_dir=Path(cast(str, options["smartschool_dir"])),
            fundamentals_dir=Path(cast(str, options["smartschool_fallback_dir"])),
            grapro_csv_dir=Path(cast(str, options["grapro_csv_dir"])),
            grapro_mdb=Path(cast(str, options["grapro_mdb"])),
            tucurricula_import_dir=Path(cast(str, options["tucurricula_import_dir"])),
            output_dir=Path(output_option) if output_option else default_output_dir(),
        )
        result = build_tusis_truth(config)
        self.stdout.write(
            self.style.SUCCESS(f"Wrote source-truth bundle: {result.output_dir}")
        )
        self.stdout.write(self.style.WARNING("No database rows were changed."))
