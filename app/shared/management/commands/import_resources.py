"""Import multiple resources from a single CSV file.

This command reads a consolidated CSV export containing data for various
models such as faculty, rooms and timetable elements. It ensures a superuser
account exists and then creates or updates database records via the admin
resources for each model.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.shared.utils import clean_column_headers
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from import_export import resources
from tablib import Dataset
from tqdm import tqdm

from app.academics.admin.resources import (  # noqa: F401
    CourseResource,
    CurriculumCourseResource,
)
from app.academics.models.college import College  # noqa: F401
from app.people.admin.resources import FacultyResource, StudentResource
from app.shared.auth.helpers import ensure_superuser  # noqa: F401
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
            ("Student", StudentResource),
            ("Faculty", FacultyResource),  # and College
            ("Room", RoomResource),  # and Space
            ("Schedule", ScheduleResource),
            ("Course", CourseResource),  # and College
            ("semester", SemesterResource),  # and Academic year
            ("CurriculumCourse", CurriculumCourseResource),
            ("Section", SectionResource),
            ("SecSession", SecSessionResource),  # and Faculty, Room and Space
        ]

        for key, ResourceClass in RESOURCES_MAP:

            resource: resources.ModelResource = ResourceClass()
            instance_loader = resource._meta.instance_loader_class(resource, dataset)
            total_rows = dataset.height

            # validation: resources.Result = resource.import_data(dataset, dry_run=True)

            # if validation.has_errors():
            #     self.stdout.write(self.style.ERROR(f"'{key}': validation errors:"))

            #     if validation.row_errors():
            #         row_index, row_err = validation.row_errors()[0]
            #         self.stdout.write(f"  row {row_index}: {row_err[0]}")
            #     if validation.base_errors:
            #         self.stdout.write(f"   {validation.base_errors[0]}")

            #     continue

            # real import
            with transaction.atomic():
                for row_number, row in enumerate(
                    tqdm(dataset.dict, total=total_rows, desc=f"Importing {key}"),
                    start=1,
                ):
                    try:
                        # import ipdb; ipdb.set_trace()

                        resource.import_row(
                            row,
                            instance_loader,
                            dry_run=False,
                            row_number=row_number,
                        )
                    except Exception as exc:
                        self.stdout.write(self.style.ERROR(f"{key} import failed: {exc}"))
                        raise (exc)

            self.stdout.write(self.style.SUCCESS(f"{key} import completed."))
