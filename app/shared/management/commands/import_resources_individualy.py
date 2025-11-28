"""Import resources from per-model CSV files located in a directory.

Each file is mapped to a ModelResource class used for validation and
insertion. Running this command requires a superuser and results in database
records being created or updated for each resource type found.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Tuple

from tqdm import tqdm

from app.registry.admin.resources import GradeResource
from app.shared.utils import clean_column_headers
from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from import_export import resources
from tablib import Dataset

from app.academics.admin.resources import (  # noqa: F401
    CourseResource,
    CurriculumCourseResource,
)
from app.people.admin.resources import FacultyResource
from app.shared.auth.helpers import ensure_superuser
from app.spaces.admin.resources import RoomResource  # noqa: F401
from app.people.admin.resources import StudentResource
from app.timetable.admin.resources.core import SemesterResource  # noqa: F401
from app.timetable.admin.resources.section import SectionResource
from app.timetable.admin.resources.session import (
    ScheduleResource,
    SecSessionResource,
)  # noqa: F401


class Command(BaseCommand):
    """Import data dumps produced by the split-csv notebook / script."""

    help = "Import resources from individual CSV files found in a directory."
    #: Mapping filename → (label, ResourceClass)
    FILEMAP: dict[str, Tuple[str, type[resources.ModelResource]]] = {
        # "um_students.csv": ("Student", StudentResource),
        # "student.csv": ("Student", StudentResource),
        # "faculty.csv": ("Faculty", FacultyResource),
        # # Staff
        # "room.csv": ("Room", RoomResource),  # + Space
        # "schedule.csv": ("Schedule", ScheduleResource),
        # "course.csv": ("Course", CourseResource),  # + College
        # "semester.csv": ("Semester", SemesterResource),  # + AcademicYear
        # "curriculum_course.csv": ("CurriculumCourse", CurriculumCourseResource),
        # "section.csv": ("Section", SectionResource),
        # "session.csv": ("SecSession", SecSessionResource),  # + Faculty / Room
        "grades-registry.csv": ("Grade", GradeResource)  # new and old ie with history tracking.
    }

    def add_arguments(self, parser: CommandParser) -> None:
        """Add the --dir option pointing to the directory of CSV files."""
        parser.add_argument(
            "-d",
            "--dir",
            default="./Seed_data/",
            help="Directory containing the per-resource CSV files.",
        )

        parser.add_argument(
            "-f",
            "--format",
            default="cs",
            help="Directory containing the per-resource CSV files.",
        )

    # ---------------------------------------------------------------- handle

    def _load_data(self, csv_path: Path, fmt: str, label=None) -> Dataset | None:
        """Read path and return a sanitised tablib.Dataset."""
        if not csv_path.exists():
            self.stdout.write(
                self.style.WARNING(f"↷ skipping {label}: {csv_path.name} missing")
            )
            return None

        dataset = Dataset().load(open(csv_path).read(), format=fmt)
        dataset = clean_column_headers(dataset)

        return dataset

    def _import_one(
        self,
        cmd: BaseCommand,
        dataset: Dataset,
        name: str,
        resource_cls: type[resources.ModelResource],
    ) -> None:
        """Run validation + import for a single resource inside its own Tx."""
        resource: resources.ModelResource = resource_cls()

        # ── dry-run validation ─────────────────────────────────────────────────
        # validation = resource.import_data(dataset, dry_run=True)
        # if validation.has_errors():
        #     cmd.stdout.write(cmd.style.ERROR(f"✖ {name}: validation errors"))
        #     if validation.row_errors():
        #         row_i, errs = validation.row_errors()[0]
        #         cmd.stdout.write(f"    row {row_i}: {errs[0]}")
        #     if validation.base_errors:
        #         cmd.stdout.write(f"    {validation.base_errors[0]}")
        #     return

        # ── real import, isolated ──────────────────────────────────────────────
        instance_loader = resource._meta.instance_loader_class(resource, dataset)
        total_rows = dataset.height
        with transaction.atomic():
            for row in tqdm(dataset.dict, total=total_rows, desc=f"Importing {name}"):
                try:
                    resource.import_row(row, instance_loader, dry_run=False)
                except Exception as exc:
                    cmd.stdout.write(cmd.style.ERROR(f"✖ {name} import failed: {exc}"))
                    return

        cmd.stdout.write(cmd.style.SUCCESS(f"✔ {name} import completed."))

    # ------------------------------------------------------------------ args
    def handle(self, *args: Any, **options: Any) -> None:
        """Execute the import for every known CSV file in the directory."""
        ensure_superuser(self)

        directory: Path = Path(options["dir"]).expanduser().resolve()
        fmt: str = options["format"]

        if not directory.is_dir():
            raise FileNotFoundError(str(directory))

        for filename, (label, resource_cls) in self.FILEMAP.items():
            csv_path = directory / filename  # add /filname to base
            dataset = self._load_data(csv_path, fmt, label)
            if dataset:
                self._import_one(self, dataset, label, resource_cls)
