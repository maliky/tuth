from __future__ import annotations

from pathlib import Path
from typing import Any, Tuple

from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from import_export import resources
from tablib import Dataset

from app.academics.admin.resources import (  # noqa: F401
    CourseResource,
    CurriculumCourseResource,
)
from app.spaces.admin.resources import RoomResource  # noqa: F401
from app.timetable.admin.resources.core import SemesterResource  # noqa: F401
from app.timetable.admin.resources.section import SectionResource
from app.timetable.admin.resources.session import SessionResource  # noqa: F401
from app.shared.management.populate_helpers.auth import ensure_superuser


class Command(BaseCommand):
    """Import data dumps produced by the *split-csv* notebook / script."""

    help = "Import resources from individual CSV files found in a directory."

    #: Mapping **filename → (label, ResourceClass)**
    FILEMAP: dict[str, Tuple[str, type[resources.ModelResource]]] = {
        "faculty.csv": ("Faculty", FacultyRessource),
        "room.csv": ("Room", RoomResource),  # + Space
        "semester.csv": ("Semester", SemesterResource),  # + AcademicYear
        "course.csv": ("Course", CourseResource),  # + College
        "curriculum_course.csv": ("CurriculumCourse", CurriculumCourseResource),
        "section.csv": ("Section", SectionResource),
        "session.csv": ("Session", SessionResource),  # + Faculty / Room
    }

    def _load_csv(self, csv_path: Path, label=None) -> Dataset | None:
        """Read *path* and return a sanitised `tablib.Dataset`."""
        if not csv_path.exists():
            self.stdout.write(
                self.style.WARNING(f"↷ skipping {label}: {csv_path.name} missing")
            )
            return None

        ds = Dataset().load(csv_path.read_text(), format="csv")
        ds.headers = [(h or "").strip() for h in ds.headers]  # strip blanks
        return ds

    def _import_one(
        self,
        cmd: BaseCommand,
        ds: Dataset,
        name: str,
        resource_cls: type[resources.ModelResource],
    ) -> None:
        """Run validation + import for a single resource inside its own Tx."""
        rsrc: resources.ModelResource = resource_cls()

        # ── dry-run validation ─────────────────────────────────────────────────
        result = rsrc.import_data(ds, dry_run=True)
        if result.has_errors():
            cmd.stdout.write(cmd.style.ERROR(f"✖ {name}: validation errors"))
            if result.row_errors():
                row_i, errs = result.row_errors()[0]
                cmd.stdout.write(f"    row {row_i}: {errs[0]}")
            if result.base_errors:
                cmd.stdout.write(f"    {result.base_errors[0]}")
            return

        # ── real import, isolated ──────────────────────────────────────────────
        try:
            with transaction.atomic():
                rsrc.import_data(ds, dry_run=False)
        except Exception as exc:
            cmd.stdout.write(cmd.style.ERROR(f"✖ {name} import failed: {exc}"))
            return

        cmd.stdout.write(cmd.style.SUCCESS(f"✔ {name} import completed."))

    # ------------------------------------------------------------------ args
    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "-d",
            "--dir",
            default="../Docs/Data/Cleaned",
            help="Directory containing the per-resource CSV files.",
        )

    # ---------------------------------------------------------------- handle
    def handle(self, *args: Any, **opts: Any) -> None:
        ensure_superuser(self)

        base_path: Path = Path(opts["dir"]).expanduser().resolve()
        if not base_path.is_dir():
            raise FileNotFoundError(str(base_path))

        for filename, (label, resource_cls) in self.FILEMAP.items():
            csv_path = base_path / filename  # add /filname to base
            ds = self._load_csv(csv_path, label)
            if ds:
                self._import_one(self, ds, label, resource_cls)
