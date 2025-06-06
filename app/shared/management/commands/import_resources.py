from __future__ import annotations

from pathlib import Path
from typing import Any

from app.spaces.admin.resources import RoomResource
from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from import_export import resources
from tablib import Dataset

from app.academics.admin.resources import CourseResource, CurriculumCourseResource
from app.timetable.admin.resources import ScheduleResource, SemesterResource


class Command(BaseCommand):
    """Load sections and schedules from ``cleaned_tscc.csv`` or provided file."""

    help = "Import resources from a CSV file"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "file_path",
            nargs="?",
            default="../Docs/Data/cleaned_tscc.csv",
            help="Path to CSV file with resources data",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        path = Path(options["file_path"])
        if not path.exists():
            raise FileNotFoundError(str(path))

        dataset = Dataset().load(open(path).read(), format="csv")

        RESOURCES_MAP: list[tuple[str, type[resources.ModelResource]]] = [
            # ("Course", CourseResource),  # and College
            # ("Room", RoomResource),  # and Space
            # ("CurriculumCourse", CurriculumCourseResource),
            # ("Semester", SemesterResource),  # and Academic year
            ("Schedule", ScheduleResource),  # and Faculty, Room and Space
        ]
        
        for key, ResourceClass in RESOURCES_MAP:
            resource: resources.ModelResource = ResourceClass()

            validation = resource.import_data(dataset, dry_run=True)

            if validation.has_errors():
                self.stdout.write(self.style.ERROR(f"'{key}': validation errors:"))
                import ipdb; ipdb.set_trace()
                if validation.row_errors():
                    row_index, row_err = validation.row_errors()[0]
                self.stdout.write(f"  row {row_index}: {row_err[0]}")
                continue

            # real import
            try:
                with transaction.atomic():
                    resource.import_data(dataset, dry_run=False)
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"{key} import failed: {exc}"))
                continue

            self.stdout.write(self.style.SUCCESS(f"{key} import completed."))
