from __future__ import annotations

from pathlib import Path
from typing import Any

from import_export import resources

from django.core.management.base import BaseCommand, CommandParser
from app.timetable.admin.resources import ScheduleResource, SemesterResource
from tablib import Dataset
from app.academics.admin.resources import CourseResource, CurriculumCourseResource


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

        RESOURCES_MAP: dict[str, type[resources.ModelResource]] = {
            "Course": CourseResource,  # and College
            # "Room": RoomResource, # and Building
            "CurriculumCourse": CurriculumCourseResource,
            "Semester": SemesterResource,  # and Academic year
            "Schedule": ScheduleResource,  # and Faculty, Room and Building
        }

        for key, ResourceClass in RESOURCES_MAP.items():
            resource: resources.ModelResource = ResourceClass()
            result = resource.import_data(dataset, dry_run=True)

            if not result.has_errors():
                resource.import_data(dataset, dry_run=False)

            self.stdout.write(self.style.SUCCESS(f"{key} import completed."))
