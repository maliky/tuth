"""Import course schedule from a CSV file.

The command expects a CSV shaped like ``cleaned_tscc.csv`` and will create
academic years, semesters, courses, instructors, schedules and sections.  It is
intended for use on an empty database when bootstrapping the system.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from app.shared.management.populate_helpers.sections import populate_sections_from_csv


class Command(BaseCommand):
    """Load sections and schedules from ``cleaned_tscc.csv`` or provided file."""

    help = "Import timetable schedule data from a CSV file"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "csv_path",
            nargs="?",
            default="/home/mlk/TU/Tuth-project/Docs/Data/cleaned_tscc.csv",
            help="Path to CSV file with schedule data",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        path = Path(options["csv_path"])
        if not path.exists():
            raise FileNotFoundError(str(path))

        with path.open() as fh:
            populate_sections_from_csv(self, fh)

        self.stdout.write(self.style.SUCCESS("Schedule import completed."))
