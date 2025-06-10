from __future__ import annotations

from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from import_export import resources
from tablib import Dataset

from app.academics.admin.resources import (  # noqa: F401
    CourseResource,
    CurriculumCourseResource,
)
from app.academics.models.college import College  # noqa: F401
from app.shared.management.populate_helpers.auth import (  # noqa: F401
    ensure_role_groups,
    ensure_superuser,
    upsert_test_users_and_roles,
)
from app.spaces.admin.resources import RoomResource  # noqa: F401
from app.timetable.admin.resources.core import SemesterResource  # noqa: F401
from app.timetable.admin.resources.section import SectionResource
from app.timetable.admin.resources.session import SessionResource  # noqa: F401


class Command(BaseCommand):
    """Load sections and sessions from ``cleaned_tscc.csv`` or provided file."""

    help = "Import resources from a CSV file"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "-f", "--file_path",
            nargs="?",
            default="../Docs/Data/cleaned_tscc.csv",
            help="Path to CSV file with resources data",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        ensure_superuser(self)

        path = Path(options["file_path"])
        if not path.exists():
            raise FileNotFoundError(str(path))

        dataset: Dataset = Dataset().load(open(path).read(), format="csv")

        # sanitize column headers: strip whitespace and drop empties
        dataset.headers = [(header or "").strip() for header in dataset.headers]

        # filter any blank column headers that may appear due to trailing commas
        while "" in dataset.headers:
            idx = dataset.headers.index("")
            dataset.headers.pop(idx)
            dataset._data = [
                tuple(value for j, value in enumerate(row) if j != idx)
                for row in dataset._data
            ]

        RESOURCES_MAP: list[tuple[str, type[resources.ModelResource]]] = [
            # ("Course", CourseResource),  # and College
            # ("Room", RoomResource),  # and Space
            # ("CurriculumCourse", CurriculumCourseResource),
            # ("Semester", SemesterResource),  # and Academic year
            # ("Session", SessionResource),  # and Faculty, Room and Space
            ("Section", SectionResource)
        ]

        for key, ResourceClass in RESOURCES_MAP:
            resource: resources.ModelResource = ResourceClass()

            validation: resources.Result = resource.import_data(dataset, dry_run=True)

            if validation.has_errors():
                self.stdout.write(self.style.ERROR(f"'{key}': validation errors:"))
                import ipdb; ipdb.set_trace()
                if validation.row_errors():
                    row_index, row_err = validation.row_errors()[0]
                    self.stdout.write(f"  row {row_index}: {row_err[0]}")
                if validation.base_errors:
                    self.stdout.write(f"   {validation.base_errors[0]}")

                continue

            # real import
            try:
                with transaction.atomic():
                    resource.import_data(dataset, dry_run=False)
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"{key} import failed: {exc}"))
                continue

            self.stdout.write(self.style.SUCCESS(f"{key} import completed."))
        # groups = ensure_role_groups()  # returns {"student": Group, …}
        # colleges = {c.code: c for c in College.objects.all()}
        # upsert_test_users_and_roles(self, colleges, groups)
