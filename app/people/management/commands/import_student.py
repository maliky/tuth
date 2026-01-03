"""Import students quickly using StudentResource with bulk operations."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from django.core.management.base import BaseCommand, CommandError, CommandParser
from tablib import Dataset

from app.people.admin.resources import StudentResource
from app.people.admin.resources_mapping import STUDENT_HEADER_MAP
from app.shared.management.commands.import_resources import _load_dataset
from app.shared.file_utils import read_text_file


class Command(BaseCommand):
    """Load students in bulk using the existing import-export resource."""

    help = "Import students from CSV/TSV files (defaults: people_students.csv, StudentInfo.csv)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "-f",
            "--file",
            action="append",
            default=None,
            help="Path(s) to CSV/TSV files; defaults to people_students.csv",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse/import without writing to the database.",
        )

    def handle(self, *args, **options) -> None:
        dry_run: bool = bool(options.get("dry_run"))
        sources: list[str] = options["file"] or [
            "Seed_data/Fundamentals/people_students.csv",
            #  "Seed_data/Fundamentals/StudentInfo.csv",
        ]

        paths = [Path(p) for p in sources]
        missing = [p for p in sources if not Path(p).exists()]
        if missing:
            raise CommandError(f"Missing source files: {', '.join(missing)}")

        text = read_text_file(paths[0])
        dataset = _load_dataset(text)
        _run_student_import(self, dataset, dry_run=dry_run)


def _run_student_import(cmd, dataset: Dataset, *, dry_run: bool = False) -> None:
    """Bulk import students in chunks with minimal logging for speed."""
    headers = dataset.headers or []
    dataset.headers = [STUDENT_HEADER_MAP.get(h, h) for h in headers]

    resource = StudentResource()
    if hasattr(resource._meta, "use_bulk"):
        resource._meta.use_bulk = True
    if hasattr(resource._meta, "use_bulk_update"):
        resource._meta.use_bulk_update = True
    if hasattr(resource._meta, "batch_size"):
        resource._meta.batch_size = 500

    chunk_size = 500
    created = updated = skipped = invalid = 0
    total_rows = len(dataset)

    for start in range(0, total_rows, chunk_size):
        end = min(start + chunk_size, total_rows)
        chunk = Dataset()

        chunk.headers = headers
        for row in dataset[start:end]:
            chunk.append(row)
        result = resource.import_data(
            chunk,
            dry_run=dry_run,
            raise_errors=True,
            use_transactions=True,
        )
        totals = getattr(result, "totals", {}) or {}
        created += totals.get("new", 0)
        updated += totals.get("update", 0)
        skipped += totals.get("skip", 0)
        invalid += totals.get("invalid", 0)
        cmd.stdout.write(
            cmd.style.NOTICE(
                f"Processed rows {start + 1}-{end} / {total_rows} "
                f"(created {created}, updated {updated}, skipped {skipped}, invalid {invalid})"
            )
        )

    summary = (
        f"Student import complete: {created} created, {updated} updated, "
        f"{skipped} skipped, {invalid} invalid."
    )
    cmd.stdout.write(cmd.style.SUCCESS(summary))
