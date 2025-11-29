"""Import multiple resources from a single CSV file.

This command reads a consolidated CSV export containing data for various
models such as faculty, rooms and timetable elements. It ensures a superuser
account exists and then creates or updates database records via the admin
resources for each model.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError, CommandParser
from import_export import resources
from import_export.results import RowResult
from tablib import Dataset
# from tqdm import tqdm  # I would like this to be used to show progress

from app.academics.admin.resources import (  # noqa: F401
    CourseResource,
    CurriculumCourseResource,
)
from app.academics.models.college import College  # noqa: F401
from app.people.admin.resources import FacultyResource, StudentResource
from app.registry.admin.resources import GradeResource
from app.shared.auth.helpers import ensure_superuser  # noqa: F401
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

    def add_arguments(self, parser: CommandParser) -> None:
        """Register --file_path CLI option for the CSV to import."""
        parser.add_argument(
            "-f",
            "--file_path",
            nargs="?",
            default="./Seed_data/cleaned_tscc.csv",
            help="Path to CSV file with resources data",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Validate and import each resource from the provided CSV."""
        ensure_superuser(self)
        call_command("load_roles", verbosity=0)

        path = Path(options["file_path"])
        if not path.exists():
            raise FileNotFoundError(str(path))

        dataset: Dataset = Dataset().load(open(path).read(), format="csv")
        dataset = clean_column_headers(dataset)

        RESOURCES_MAP: list[tuple[str, type[resources.ModelResource]]] = [
            # ("Student", StudentResource),
            # ("Faculty", FacultyResource),  # and College
            # ("Room", RoomResource),  # and Space
            # ("Schedule", ScheduleResource),
            # ("Course", CourseResource),  # and College
            # ("semester", SemesterResource),  # and Academic year
            # ("CurriculumCourse", CurriculumCourseResource),
            # ("Section", SectionResource),
            # ("SecSession", SecSessionResource),  # and Faculty, Room and Space
            ("Grade", GradeResource), # Student, Semester, CurriculumCourse, grade
        ]

        for key, ResourceClass in RESOURCES_MAP:
            resource: resources.ModelResource = ResourceClass()
            self.stdout.write(f"Importing {key}…")
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
                    f"{key} import failed with {error_rows} errors "
                    f"and {invalid_rows} invalid rows."
                )

            created = result.totals[RowResult.IMPORT_TYPE_NEW]
            updated = result.totals[RowResult.IMPORT_TYPE_UPDATE]
            self.stdout.write(
                self.style.SUCCESS(
                    f"{key} import completed: {created} created, {updated} updated."
                )
            )
