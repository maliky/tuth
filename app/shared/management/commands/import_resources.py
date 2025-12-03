"""Import multiple resources from a single CSV file.

This command reads a consolidated CSV export containing data for various
models such as faculty, rooms and timetable elements. It ensures a superuser
account exists and then creates or updates database records via the admin
resources for each model.
"""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Any, Iterable, Sequence

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction
from import_export import resources
from import_export.results import RowResult
from tablib import Dataset
from tablib.core import InvalidDimensions
from tqdm import tqdm

from app.academics.admin.resources import (  # noqa: F401
    CourseResource,
    CurriculumCourseResource,
)
from app.academics.models.college import College  # noqa: F401
from app.people.admin.resources import FacultyResource, StudentResource, DonorResource
from app.registry.admin.resources import GradeResource
from app.registry.admin.resources_legacy import (
    LegacyGradeSheetResource,
    LegacyRegistrationResource,
)
from app.shared.auth.helpers import ensure_superuser  # noqa: F401
from app.shared.file_utils import guess_tabular_format, read_text_file
from app.shared.types import DirectoryResourceEntry, ModelResourceType
from app.shared.utils import clean_column_headers
from app.spaces.admin.resources import RoomResource  # noqa: F401
from app.timetable.admin.resources.core import SemesterResource  # noqa: F401
from app.timetable.admin.resources.section import SectionResource
from app.timetable.admin.resources.session import (
    ScheduleResource,
    SecSessionResource,
)  # noqa: F401


class Command(BaseCommand):
    """Load sections and sessions from cleaned_tscc.csv or provided file."""

    help = "Import resources from a CSV file"

    RESOURCE_REGISTRY: dict[str, ModelResourceType] = {
        "Grade": GradeResource,
        "LegacyGrade": LegacyGradeSheetResource,
        "LegacyRegistration": LegacyRegistrationResource,
    }
    DIRECTORY_RESOURCES: Sequence[DirectoryResourceEntry] = (
        ("Faculty", FacultyResource, ("people_instructors.csv",)),
        ("Room", RoomResource, ("space_room.csv",)),
        ("Course", CourseResource, ("academic_course.csv",)),
        (
            "CurriculumCourse",
            CurriculumCourseResource,
            ("academic_curriculum_course.csv",),
        ),
        (
            "Semester",
            SemesterResource,
            ("academicyear_semester.csv",),
        ),
        ("Donor", DonorResource, ("people_donors.csv",)),
        (
            "Student",
            StudentResource,
            (
                # StudentInfo.csv  # may  have usefull info
                "people_students.csv",
                "UM_students.csv",
            ),
        ),
        (
            "Grade",
            GradeResource,
            (
                "registry_gradeSheets.csv",
                "gradesheets.csv",
            ),
        ),
    )
    LEGACY_DIRECTORY_RESOURCES: Sequence[DirectoryResourceEntry] = (
        (
            "LegacyRegistration",
            LegacyRegistrationResource,
            (
                "registry_registration.csv",
                "studentcourses.csv",
                "UM_StudentsCourses.csv",
            ),
        ),
        (
            "LegacyGrade",
            LegacyGradeSheetResource,
            (
                # "registry_gradeSheets.csv",
                # "gradesheets.csv",
                "oldgrades.csv",
                "UM_TransferGrades.csv",
            ),
        ),
    )
    RESOURCE_CHOICES = tuple(
        OrderedDict.fromkeys(
            list(RESOURCE_REGISTRY.keys())
            + [key for key, *_ in DIRECTORY_RESOURCES]
            + [key for key, *_ in LEGACY_DIRECTORY_RESOURCES]
        ).keys()
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
            "-r",
            "--resource",
            action="append",
            choices=self.RESOURCE_CHOICES,
            help="Limit import to the selected resource(s). Can be repeated.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Validate and import each resource from the provided CSV."""
        call_command("migrate", interactive=False, verbosity=0)
        call_command("create_states")
        ensure_superuser(self)
        call_command("load_roles", verbosity=0)

        path = Path(options["file_path"])
        selected = options.get("resource")
        if not path.exists():
            raise FileNotFoundError(str(path))

        if path.is_dir():
            self._import_from_directory(path, selected)
            return

        file_contents = read_text_file(path)
        try:
            dataset: Dataset = Dataset().load(
                file_contents, format=guess_tabular_format(file_contents)
            )
        except InvalidDimensions:
            if selected and len(selected) == 1 and selected[0] == "Donor":
                dataset = self._build_donor_dataset(file_contents)
            else:
                raise
        dataset = clean_column_headers(dataset)

        # > Where is options comming form ?
        selected_keys = selected or list(self.RESOURCE_REGISTRY.keys())

        for key in selected_keys:
            if key not in self.RESOURCE_REGISTRY:
                raise CommandError(
                    f"Resource '{key}' is only available when importing from a directory."
                )
            ResourceClass = self.RESOURCE_REGISTRY[key]
            self._run_import(dataset, key, ResourceClass)

    # ------------------------------------------------------------------ helpers

    def _run_import(
        self,
        dataset: Dataset,
        label: str,
        ResourceClass: ModelResourceType,
    ) -> None:
        """Execute the import for a dataset/resource pair with progress output."""
        resource: resources.ModelResource = ResourceClass()
        rows = list(dataset.dict)
        total_rows = len(rows)
        instance_loader = resource._meta.instance_loader_class(resource, dataset)
        created = 0
        updated = 0
        error_rows: list[tuple[int, list[Exception]]] = []
        invalid_rows: list[tuple[int, str]] = []

        with transaction.atomic():
            for row_number, row in enumerate(
                tqdm(rows, total=total_rows or None, desc=f"Importing {label}"),
                start=1,
            ):
                try:
                    row_result = resource.import_row(
                        row,
                        instance_loader,
                        dry_run=False,
                        row_number=row_number,
                    )
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
            if resource._meta.use_bulk:
                resource.bulk_create(
                    using_transactions=True,
                    dry_run=False,
                    raise_errors=True,
                )
                resource.bulk_update(
                    using_transactions=True,
                    dry_run=False,
                    raise_errors=True,
                )
                resource.bulk_delete(
                    using_transactions=True,
                    dry_run=False,
                    raise_errors=True,
                )

        if error_rows or invalid_rows:
            for row_number, errors in error_rows[:5]:
                first = errors[0] if errors else None
                if first is not None:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Row {row_number} failed: {getattr(first, 'error', first)}"
                        )
                    )
            for row_number, error in invalid_rows[:5]:
                self.stdout.write(self.style.ERROR(f"Row {row_number} invalid: {error}"))
            raise CommandError(
                f"{label} import failed with {len(error_rows)} errors "
                f"and {len(invalid_rows)} invalid rows."
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"{label} import completed: {created} created, {updated} updated."
            )
        )

    def _import_from_directory(self, directory: Path, selected: list[str] | None) -> None:
        """Load individual CSV files found in a directory."""
        if selected:
            targets = selected
        else:
            targets = [name for name, *_ in self.DIRECTORY_RESOURCES]

        target_set = set(targets)
        ordered = list(self.DIRECTORY_RESOURCES) + list(self.LEGACY_DIRECTORY_RESOURCES)

        for name, ResourceClass, filenames in ordered:
            if name not in target_set:
                continue

            dataset = self._load_directory_dataset(directory, filenames)
            if dataset is None:
                self.stdout.write(
                    self.style.WARNING(f"↷ skipping {name}: {filenames} not found")
                )
                continue

            self._run_import(dataset, name, ResourceClass)

    def _load_directory_dataset(
        self, directory: Path, filenames: Iterable[str]
    ) -> Dataset | None:
        """Return a dataset for the first matching CSV in filenames."""
        for name in filenames:
            file_path = directory / name
            if not file_path.exists():
                continue
            contents = read_text_file(file_path)
            try:
                dataset = Dataset().load(contents, format=guess_tabular_format(contents))
            except InvalidDimensions:
                dataset = self._build_donor_dataset(contents)
            return clean_column_headers(dataset)
        return None

    def _build_donor_dataset(self, text: str) -> Dataset:
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
