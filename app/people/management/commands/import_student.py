"""Import students quickly using StdResource with bulk operations."""

from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Mapping, TypeAlias

from django.core.management.base import BaseCommand, CommandError, CommandParser
from tablib import Dataset

from app.people.admin.resources import StdResource
from app.people.admin.resources_mapping import STUDENT_HEADER_MAP
from app.shared.file_utils import read_text_file
from app.shared.management.commands.import_resources import _load_dataset

ErrorRowT: TypeAlias = Mapping[str, str]


class Command(BaseCommand):
    """Load students in bulk using the existing import-export resource."""

    help = "Import students from CSV/TSV files (defaults: people_students.csv, StudentInfo.csv)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "-f",
            "--file",
            default="Seed_data/Fundamentals/people_full_student.tsv",
            help="Path(s) to CSV/TSV files; defaults to people_full_student.tsv",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse/import without writing to the database.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Batch size for chunked student import (default: 1000).",
        )
        parser.add_argument(
            "--start-row",
            type=int,
            default=1,
            help="1-based data row to start importing from for resume runs.",
        )

    def handle(self, *args, **options) -> None:
        dry_run: bool = bool(options.get("dry_run"))
        path: Path = Path(options["file"])
        if not path.exists():
            raise CommandError(f"Missing source files: {path}")

        text = read_text_file(path)
        dataset = _load_dataset(text)
        batch_size = int(options.get("batch_size") or 500)
        start_row = max(1, int(options.get("start_row") or 1))
        _run_std_import(
            self,
            dataset,
            dry_run=dry_run,
            batch_size=batch_size,
            start_row=start_row,
        )


def _run_std_import(
    cmd,
    dataset: Dataset,
    *,
    dry_run: bool = False,
    batch_size: int = 500,
    start_row: int = 1,
) -> None:
    """Bulk import students in chunks with minimal logging for speed."""
    headers = dataset.headers or []
    dataset.headers = [STUDENT_HEADER_MAP.get(h, h) for h in headers]

    resource = StdResource()
    if hasattr(resource._meta, "use_bulk"):
        resource._meta.use_bulk = True
    if hasattr(resource._meta, "use_bulk_update"):
        resource._meta.use_bulk_update = True
    if hasattr(resource._meta, "batch_size"):
        resource._meta.batch_size = batch_size

    chunk_size = batch_size
    created = updated = skipped = invalid = 0
    total_rows = len(dataset)
    start_index = max(0, start_row - 1)

    for start in range(start_index, total_rows, chunk_size):
        end = min(start + chunk_size, total_rows)
        chunk = Dataset()

        chunk.headers = headers
        for row in dataset[start:end]:
            chunk.append(row)
        t0 = time.perf_counter()
        try:
            result = resource.import_data(
                chunk,
                dry_run=dry_run,
                raise_errors=True,
                use_transactions=True,
            )
        except Exception as exc:
            _log_chunk_error(cmd, chunk, start, str(exc))
            raise
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
        f"Student import complete: {created} created, {updated} updated, "
        f"{skipped} skipped, {invalid} invalid."
    )
    cmd.stdout.write(cmd.style.SUCCESS(summary))


def _log_chunk_error(
    cmd, chunk: Dataset, start_index: int, error: str, *, limit: int = 100
) -> None:
    """Log actual offending rows when a chunk fails."""
    failing_rows = _find_failing_student_rows(chunk, start_index, limit=limit)
    if not failing_rows:
        failing_rows = [
            (
                start_index + idx + 1,
                error,
                {key: row.get(key, "") for key in list(chunk.headers or [])},
            )
            for idx, row in enumerate(chunk.dict[:limit])
        ]

    log_path = Path("logs/import_errors/import_student_errors.csv")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    headers = list(chunk.headers or [])
    fieldnames = ["row_number", "error", *headers]

    mode = "a" if log_path.exists() else "w"
    with log_path.open(mode, newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        if mode == "w":
            writer.writeheader()
        for row_number, row_error, row in failing_rows:
            payload: dict[str, object] = {k: row.get(k, "") for k in headers}
            payload["row_number"] = row_number
            payload["error"] = row_error
            writer.writerow(payload)

    cmd.stdout.write(
        cmd.style.ERROR(
            f"Chunk starting at row {start_index + 1} failed: {error}; "
            f"logged {len(failing_rows)} failing/sample rows to {log_path}"
        )
    )


def _find_failing_student_rows(
    chunk: Dataset, start_index: int, *, limit: int
) -> list[tuple[int, str, ErrorRowT]]:
    """Dry-run each row in a failed chunk to isolate real row-level errors."""
    failures: list[tuple[int, str, ErrorRowT]] = []
    headers = list(chunk.headers or [])
    for offset, row in enumerate(chunk.dict):
        if len(failures) >= limit:
            break
        one = Dataset(headers=headers)
        one.append([row.get(header, "") for header in headers])
        try:
            StdResource().import_data(one, dry_run=True, raise_errors=True)
        except Exception as exc:  # noqa: BLE001 - diagnostics should preserve importer errors.
            failures.append((start_index + offset + 1, str(exc), row))
    return failures
