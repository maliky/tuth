"""Snapshot current TUSIS data and reconcile it with TUCurricula TSVs."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from django.core.management.base import BaseCommand, CommandError, CommandParser

from app.academics.catalog_reconciliation import write_catalog_reconciliation
from app.academics.current_data_snapshot import write_current_data_snapshot
from app.academics.current_usage import load_current_usage


class Command(BaseCommand):
    """Generate non-destructive current-data snapshots and reconciliation reports."""

    help = (
        "Compare current TUSIS academic catalog rows with org-derived TUCurricula "
        "import TSVs. The command writes reports only; it does not mutate database rows."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        """Register reconciliation command options."""
        parser.add_argument(
            "--import-dir",
            default="data/tucurricula_import",
            help="Directory containing academic_course/curriculum/curriculum_course TSVs.",
        )
        parser.add_argument(
            "--output-dir",
            default=None,
            help="Report directory. Defaults to logs/tucurricula_reconciliation/<timestamp>.",
        )
        parser.add_argument(
            "--snapshot-only",
            action="store_true",
            help="Write current-data snapshots but skip org/current comparison reports.",
        )
        parser.add_argument(
            "--skip-snapshot",
            action="store_true",
            help="Write comparison reports without current operational snapshot files.",
        )

    def handle(self, *args: object, **options: object) -> None:
        """Write snapshots/reports for the selected database and import directory."""
        import_dir = Path(cast(str, options["import_dir"])).expanduser()
        output_dir = _resolve_output_dir(cast(str | None, options.get("output_dir")))
        snapshot_only = bool(options.get("snapshot_only"))
        skip_snapshot = bool(options.get("skip_snapshot"))

        if snapshot_only and skip_snapshot:
            raise CommandError("--snapshot-only and --skip-snapshot cannot be combined.")
        _validate_import_dir(import_dir, require_catalog=not snapshot_only)

        output_dir.mkdir(parents=True, exist_ok=True)
        usage = load_current_usage()
        snapshot_counts: dict[str, int] = {}
        reconciliation_counts: dict[str, int] = {}

        if not skip_snapshot:
            snapshot_counts = write_current_data_snapshot(output_dir, usage).counts
        if not snapshot_only:
            reconciliation_counts = write_catalog_reconciliation(
                import_dir, output_dir, usage
            ).counts

        _write_summary(
            output_dir=output_dir,
            import_dir=import_dir,
            snapshot_counts=snapshot_counts,
            reconciliation_counts=reconciliation_counts,
        )
        self.stdout.write(
            self.style.SUCCESS(f"Wrote reconciliation reports: {output_dir}")
        )
        self.stdout.write(self.style.WARNING("No database rows were changed."))


def _resolve_output_dir(raw_output_dir: str | None) -> Path:
    """Return explicit output dir or a timestamped ignored logs directory."""
    if raw_output_dir:
        return Path(raw_output_dir).expanduser()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("logs") / "tucurricula_reconciliation" / stamp


def _validate_import_dir(import_dir: Path, *, require_catalog: bool) -> None:
    """Ensure required org-derived TSVs exist before comparison."""
    if not import_dir.exists():
        raise CommandError(f"Import directory does not exist: {import_dir}")
    if not require_catalog:
        return
    required = (
        "academic_course.tsv",
        "academic_curriculum.tsv",
        "academic_curriculum_course.tsv",
    )
    missing = [filename for filename in required if not (import_dir / filename).exists()]
    if missing:
        raise CommandError(f"Missing import TSVs in {import_dir}: {', '.join(missing)}")


def _write_summary(
    *,
    output_dir: Path,
    import_dir: Path,
    snapshot_counts: dict[str, int],
    reconciliation_counts: dict[str, int],
) -> None:
    """Write a human-readable summary and the safe apply sequence."""
    lines = [
        "TUCurricula reconciliation report",
        f"import_dir: {import_dir}",
        f"output_dir: {output_dir}",
        "mutation: none",
        "",
        "snapshot_counts:",
    ]
    lines.extend(f"  {name}: {count}" for name, count in sorted(snapshot_counts.items()))
    lines.extend(["", "reconciliation_counts:"])
    lines.extend(
        f"  {name}: {count}" for name, count in sorted(reconciliation_counts.items())
    )
    lines.extend(
        [
            "",
            "safe_update_sequence:",
            "  1. Review current_* TSV snapshots and keep them outside git.",
            "  2. Import org-derived Course, Curriculum, CurriCrs, and requirements in dry-run.",
            "  3. Apply non-destructive upserts only for org_only rows.",
            "  4. Update metadata_diff rows only when action is not review_referenced_*.",
            "  5. Preserve current_only rows with usage_total > 0 until student records are remapped.",
            "  6. Archive unreferenced current_only rows only after dean/registrar review.",
        ]
    )
    (output_dir / "SUMMARY.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
