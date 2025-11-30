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
from import_export import resources
from import_export.results import RowResult
from tablib import Dataset

from app.academics.admin.resources import (  # noqa: F401
    CourseResource,
    CurriculumCourseResource,
)
from app.academics.models.college import College  # noqa: F401
from app.people.admin.resources import FacultyResource, StudentResource
from app.registry.admin.resources import GradeResource
from app.registry.admin.resources_legacy import (
    LegacyGradeSheetResource,
    LegacyRegistrationResource,
)
from app.shared.auth.helpers import ensure_superuser  # noqa: F401
from app.shared.file_utils import guess_tabular_format, read_text_file
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

    RESOURCE_REGISTRY: dict[str, tuple[str, type[resources.ModelResource]]] = {
        "grade": ("Grade", GradeResource),
        "legacy_grade": ("LegacyGrade", LegacyGradeSheetResource),
        "legacy_registration": ("LegacyRegistration", LegacyRegistrationResource),
    }
    DIRECTORY_RESOURCES: Sequence[
        tuple[str, str, type[resources.ModelResource], tuple[str, ...]]
    ] = (
        ("faculty", "Faculty", FacultyResource, ("people_instructors.csv",)),
        ("room", "Room", RoomResource, ("space_room.csv",)),
        ("course", "Course", CourseResource, ("academic_course.csv",)),
        (
            "curriculum_course",
            "CurriculumCourse",
            CurriculumCourseResource,
            ("academic_curriculum_course.csv",),
        ),
        (
            "semester",
            "Semester",
            SemesterResource,
            ("academicyear_semester.csv",),
        ),
        (
            "student",
            "Student",
            StudentResource,
            (
                "people_students.head.csv",
                "UM_students.head.csv",
            ),
        ),
    )
    LEGACY_DIRECTORY_RESOURCES: Sequence[
        tuple[str, str, type[resources.ModelResource], tuple[str, ...]]
    ] = (
        (
            "legacy_registration",
            "LegacyRegistration",
            LegacyRegistrationResource,
            (
                # > do not add the full csv (withouth head)
                "registry_registration.head.csv",
                "studentcourses.head.csv",
                "UM_StudentsCourses.head.csv",
            ),
        ),
        (
            "legacy_grade",
            "LegacyGrade",
            LegacyGradeSheetResource,
            (
                "registry_gradeSheets.head.csv",
                "gradesheets.head.csv",
                "oldgrades.head.csv",
                "UM_GradeSheet.head.csv",
                "UM_TransferGrades.head.csv",
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
        ensure_superuser(self)
        call_command("load_roles", verbosity=0)

        path = Path(options["file_path"])
        if not path.exists():
            raise FileNotFoundError(str(path))

        if path.is_dir():
            self._import_from_directory(path, selected)
            return

        file_contents = read_text_file(path)
        dataset: Dataset = Dataset().load(
            file_contents, format=guess_tabular_format(file_contents)
        )
        dataset = clean_column_headers(dataset)

        # > Where is options comming form ?
        selected_keys = options.get("resource") or list(self.RESOURCE_REGISTRY.keys())

        for key in selected_keys:
            if key not in self.RESOURCE_REGISTRY:
                raise CommandError(
                    f"Resource '{key}' is only available when importing from a directory."
                )
            label, ResourceClass = self.RESOURCE_REGISTRY[key]
            self._run_import(dataset, label, ResourceClass)

    # ------------------------------------------------------------------ helpers

    def _run_import(
        self,
        dataset: Dataset,
        label: str,
        ResourceClass: type[resources.ModelResource],
    ) -> None:
        """Execute the import for a dataset/resource pair."""
        resource: resources.ModelResource = ResourceClass()
        self.stdout.write(f"Importing {label}…")
        result = resource.import_data(dataset, dry_run=False)

        error_rows = result.totals[RowResult.IMPORT_TYPE_ERROR]
        invalid_rows = result.totals[RowResult.IMPORT_TYPE_INVALID]

        if error_rows or invalid_rows:
            for idx, errors in result.row_errors()[:5]:
                first = errors[0] if errors else None
                if first is not None:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Row {idx} failed: {getattr(first, 'error', first)}"
                        )
                    )
            for invalid in result.invalid_rows[:5]:
                self.stdout.write(
                    self.style.ERROR(f"Row {invalid.number} invalid: {invalid.error}")
                )
            raise CommandError(
                f"{label} import failed with {error_rows} errors "
                f"and {invalid_rows} invalid rows."
            )

        created = result.totals[RowResult.IMPORT_TYPE_NEW]
        updated = result.totals[RowResult.IMPORT_TYPE_UPDATE]
        self.stdout.write(
            self.style.SUCCESS(
                f"{label} import completed: {created} created, {updated} updated."
            )
        )

    def _import_from_directory(
        self, directory: Path, selected: list[str] | None
    ) -> None:
        """Load individual CSV files found in a directory."""
        if selected:
            targets = selected
        else:
            targets = [key for key, *_ in self.DIRECTORY_RESOURCES]

        target_set = set(targets)
        ordered = list(self.DIRECTORY_RESOURCES) + list(self.LEGACY_DIRECTORY_RESOURCES)

        for key, label, ResourceClass, filenames in ordered:
            if key not in target_set:
                continue

            dataset = self._load_directory_dataset(directory, filenames)
            if dataset is None:
                self.stdout.write(
                    self.style.WARNING(f"↷ skipping {label}: file not found")
                )
                continue

            self._run_import(dataset, label, ResourceClass)

    def _load_directory_dataset(
        self, directory: Path, filenames: Iterable[str]
    ) -> Dataset | None:
        """Return a dataset for the first matching CSV in filenames."""
        for name in filenames:
            file_path = directory / name
            if not file_path.exists():
                continue
            contents = read_text_file(file_path)
            dataset = Dataset().load(contents, format=guess_tabular_format(contents))
            return clean_column_headers(dataset)
        return None
