"""Import multiple resources from a single CSV file.

This command reads a consolidated CSV export containing data for various
models such as faculty, rooms and timetable elements. It ensures a superuser
account exists and then creates or updates database records via the admin
resources for each model.
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from pathlib import Path
from typing import Any, Iterable, Sequence

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import IntegrityError, transaction
from import_export import resources
from import_export.results import RowResult
from tablib import Dataset
from tablib.core import InvalidDimensions
from tqdm import tqdm

from app.academics.admin import (  # noqa: F401
    CourseResource,
    CurriculumCourseResource,
)
from app.academics.models import College  # noqa: F401
from app.people.admin import DonorResource, FacultyResource, StudentResource
from app.registry.admin import (
    GradeResource,
    LegacyGradeSheetResource,
    LegacyRegistrationResource,
)
from app.shared.auth.helpers import ensure_superuser  # noqa: F401
from app.shared.file_utils import guess_tabular_format, read_text_file
from app.shared.importing.logging_utils import get_import_logger
from app.shared.management.resources import (
    DIRECTORY_RESOURCES,
    LEGACY_DIRECTORY_RESOURCES,
    RESOURCE_CHOICES,
    RESOURCE_REGISTRY,
)
from app.shared.types import DirectoryResourceEntry, ModelResourceType
from app.shared.utils import clean_column_headers
from app.spaces.admin import RoomResource  # noqa: F401
from app.timetable.admin.resources import (
    ScheduleResource,
    SecSessionResource,
    SectionResource,
    SemesterResource,
)  # noqa: F401


class Command(BaseCommand):
    """Load sections and sessions from cleaned_tscc.csv or provided file."""

    help = (
        "Import resources from a CSV file or directory.\n\n"
        "Arguments:\n"
        "  -f/--file_path: path to a CSV/TSV or a directory containing resources.\n"
        "  -r/--resource: optional, one or more resource names to limit the import "
        "(defaults to all available). Choices include Grade, LegacyGrade, LegacyRegistration "
        "and directory-scoped resources (Faculty, Room, Course, CurriculumCourse, Semester, "
        "Donor, Student, Grade, LegacyRegistration, LegacyGrade).\n"
        "Behavior:\n"
        "  • Reads tabular data, normalizes headers, and delegates to import-export resources.\n"
        "  • Emits progress to stdout and logs start/end with counts to the import logger.\n"
        "  • Skips rows/resources gracefully when hooks are provided (should_skip_row, "
        "handle_integrity_error, post_import_report).\n"
    )

    def add_arguments(self, parser: CommandParser) -> None:
        """Register --file_path CLI option for the CSV to import."""
        parser.add_argument(
            "-f",
            "--file_path",
            nargs="?",
            default="./Seed_data/cleaned_tscc.csv",
            help="Path to CSV file with resources data",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse/import without writing to the database.",
        )

        parser.add_argument(
            "-r",
            "--resource",
            action="append",
            choices=self.RESOURCE_CHOICES,
            help="Limit import to the selected resource(s). Can be repeated.",
        )

    def handle(self, *args: Any, **opts: Any) -> None:
        """Validate and import each resource from the provided CSV."""
        path = Path(opts["file_path"])
        selected = opts.get("resource")
        dry_run = opts.get("dry_run")
        if not path.exists():
            raise FileNotFoundError(str(path))

        if path.is_dir():
            _import_from_directory(self, path, selected, dry_run)
            return

        file_contents = read_text_file(path)
        dataset = _load_dataset(selected, file_contents)

        selected_keys = selected or list(RESOURCE_REGISTRY.keys())

        for key in selected_keys:
            if key not in RESOURCE_REGISTRY:
                raise CommandError(
                    f"Resource '{key}' is only available when importing from a directory."
                )
            ResourceClass = RESOURCE_REGISTRY[key]
            _run_import(self, dataset, key, ResourceClass, dry_run)


# ------------------------------------------------------------------ helpers


def _run_import(
    cmd,
    dataset: Dataset,
    label: str,
    ResourceClass: ModelResourceType,
    dry_run: bool = False,
) -> None:
    """Execute the import for a dataset/resource pair with progress output."""
    resource: resources.ModelResource = ResourceClass()
    logger = get_import_logger()
    rows = list(dataset.dict)
    total_rows = len(rows)
    instance_loader = resource._meta.instance_loader_class(resource, dataset)
    created = 0
    updated = 0
    error_rows: list[tuple[int, list[Exception]]] = []
    invalid_rows: list[tuple[int, str]] = []

    logger.info(f"Starting import for {label}", extra={"resource": label})
    with transaction.atomic():
        for row_number, row in enumerate(
            tqdm(rows, total=total_rows or None, desc=f"Importing {label}"),
            start=1,
        ):
            skip_check = getattr(resource, "should_skip_row", None)
            if skip_check and skip_check(row, row_number, command=cmd):
                continue
            try:
                row_result = resource.import_row(
                    row,
                    instance_loader,
                    dry_run=dry_run,
                    row_number=row_number,
                )
            except IntegrityError as exc:
                handler = getattr(resource, "handle_integrity_error", None)
                if handler and handler(exc, row, row_number, command=cmd):
                    continue
                raise CommandError(
                    f"{label} import failed at row {row_number}: {exc}"
                ) from exc
            except Exception as exc:
                raise CommandError(
                    f"{label} import failed at row {row_number}: {exc}"
                ) from exc

            if row_result.import_type == RowResult.IMPORT_TYPE_NEW:
                created += 1
            elif row_result.import_type == RowResult.IMPORT_TYPE_UPDATE:
                updated += 1
            elif row_result.import_type == RowResult.IMPORT_TYPE_INVALID:
                invalid_rows.append(
                    (row_number, getattr(row_result, "error", "Invalid row"))
                )

            if row_result.errors:
                error_rows.append((row_number, row_result.errors))

        # > Explain the code below.  How does it not delete everything
        # > on each pass ?
        if resource._meta.use_bulk and not dry_run:
            resource.bulk_create(
                using_transactions=True,
                dry_run=dry_run,
                raise_errors=True,
            )
            resource.bulk_update(
                using_transactions=True,
                dry_run=dry_run,
                raise_errors=True,
            )
            resource.bulk_delete(
                using_transactions=True,
                dry_run=dry_run,
                raise_errors=True,
            )

        if dry_run:
            transaction.set_rollback(True)

    if error_rows or invalid_rows:
        for row_number, errors in error_rows[:5]:
            first = errors[0] if errors else None
            if first is not None:
                cmd.stdout.write(
                    cmd.style.ERROR(
                        f"Row {row_number} failed: {getattr(first, 'error', first)}"
                    )
                )
        for row_number, error in invalid_rows[:5]:
            cmd.stdout.write(cmd.style.ERROR(f"Row {row_number} invalid: {error}"))
        raise CommandError(
            f"{label} import failed with {len(error_rows)} errors "
            f"and {len(invalid_rows)} invalid rows."
        )

    cmd.stdout.write(
        cmd.style.SUCCESS(
            f"{label} import completed{' (dry-run)' if dry_run else ''}: {created} created, {updated} updated."
        )
    )
    reporter = getattr(resource, "post_import_report", None)
    if reporter:
        reporter(cmd)
    logger.info(
        f"Completed import for {label}",
        extra={
            "resource": label,
            "created_count": created,
            "updated_count": updated,
            "error_count": len(error_rows),
            "invalid_count": len(invalid_rows),
        },
    )


def _import_from_directory(
    cmd, directory: Path, selected: list[str] | None, dry_run: bool = False
) -> None:
    """Load individual CSV files found in a directory."""
    if selected:
        targets = selected
    else:
        targets = [name for name, *_ in DIRECTORY_RESOURCES]

    target_set = set(targets)
    ordered = list(DIRECTORY_RESOURCES) + list(LEGACY_DIRECTORY_RESOURCES)

    for name, ResourceClass, filenames in ordered:
        if name not in target_set:
            continue

        dataset = _load_directory_dataset(directory, filenames)
        if dataset is None:
            cmd.stdout.write(
                cmd.style.WARNING(f"↷ skipping {name}: {filenames} not found")
            )
            continue

        cmd._run_import(dataset, name, ResourceClass, dry_run)


def _load_directory_dataset(directory: Path, filenames: Iterable[str]) -> Dataset | None:
    """Return a dataset for the first matching CSV in filenames."""
    for name in filenames:
        file_path = directory / name
        if not file_path.exists():
            continue
        contents = read_text_file(file_path)
        try:
            dataset = Dataset().load(contents, format=guess_tabular_format(contents))
        except InvalidDimensions:
            dataset = _build_donor_dataset(contents)
        return clean_column_headers(dataset)
    return None


def _build_donor_dataset(text: str) -> Dataset:
    """Create a single-column dataset from donor CSV text."""
    dataset = Dataset(headers=["donors"])
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines and lines[0].lower().startswith("donor"):
        lines = lines[1:]
    for value in lines:
        cleaned = value.strip().strip('"')
        if cleaned:
            dataset.append([cleaned])
    return dataset


def _load_dataset(selected, file_contents) -> Dataset:
    """Load the c/tsv file in Dataset handling special Donor case."""
    try:
        dataset: Dataset = Dataset().load(
            file_contents, format=guess_tabular_format(file_contents)
        )
    except InvalidDimensions:
        if selected and len(selected) == 1 and selected[0] == "Donor":
            dataset = _build_donor_dataset(file_contents)
        else:
            raise

    cleaned_dataset = clean_column_headers(dataset)

    return cleaned_dataset
