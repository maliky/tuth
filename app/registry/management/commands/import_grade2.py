"""Batch grade importer using GradeResource with chunked processing."""

from __future__ import annotations

import time
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError, CommandParser
from tablib import Dataset

from app.registry.admin.resources import GradeResource
from app.shared.management.commands.import_resources import _load_dataset


class Command(BaseCommand):
    """Import grades via GradeResource with configurable chunked batching."""

    help = "Import grades from CSV/TSV using GradeResource with chunked batching."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "-f",
            "--file",
            default="Seed_data/Fundamentals/full_grades.tsv",
            help="Path to CSV/TSV file containing grades.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse/import without writing to the database.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Number of rows per import batch (default: 1000).",
        )

    def handle(self, *args, **options) -> None:
        file_path = Path(options["file"])
        if not file_path.exists():
            raise CommandError(f"Missing file: {file_path}")

        dry_run: bool = bool(options.get("dry_run"))
        batch_size: int = int(options.get("batch_size") or 1000)

        file_contents = file_path.read_text(encoding="utf-8")
        dataset = _load_dataset(file_contents)

        _run_grade_import(self, dataset, dry_run=dry_run, batch_size=batch_size)


def _run_grade_import(
    cmd, dataset: Dataset, *, dry_run: bool = False, batch_size: int = 1000
) -> None:
    """Import grades in chunks using GradeResource."""
    headers = dataset.headers or []
    resource = GradeResource()
    if hasattr(resource._meta, "batch_size"):
        resource._meta.batch_size = batch_size

    created = updated = skipped = invalid = 0
    total_rows = len(dataset)

    for start in range(0, total_rows, batch_size):
        end = min(start + batch_size, total_rows)
        chunk = Dataset()
        chunk.headers = headers
        for row in dataset[start:end]:
            chunk.append(row)

        t0 = time.perf_counter()
        result = resource.import_data(
            chunk,
            dry_run=dry_run,
            raise_errors=True,
            use_transactions=True,
        )
        elapsed = time.perf_counter() - t0
        rows_processed = end - start
        sec_per_row = elapsed / rows_processed if rows_processed else 0.0

        totals = getattr(result, "totals", {}) or {}
        created += totals.get("new", 0)
        updated += totals.get("update", 0)
        skipped += totals.get("skip", 0)
        invalid += totals.get("invalid", 0)

        cmd.stdout.write(
            cmd.style.NOTICE(
                f"Processed rows {start + 1}-{end} / {total_rows} "
                f"(created {created}, updated {updated}, skipped {skipped}, invalid {invalid}) "
                f"[{sec_per_row:.4f} sec/row]"
            )
        )

    summary = (
        f"Grade import complete: {created} created, {updated} updated, "
        f"{skipped} skipped, {invalid} invalid."
    )
    cmd.stdout.write(cmd.style.SUCCESS(summary))
