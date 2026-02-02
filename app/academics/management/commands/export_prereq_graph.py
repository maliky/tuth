"""Export curriculum prerequisite data as CSV + Graphviz DOT."""

from __future__ import annotations

import csv
import shutil
import subprocess
from pathlib import Path
from typing import Iterable, Sequence, TypeAlias

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.utils.text import slugify

from app.academics.prereq_graph import (
    export_prereq_graph,
    resolve_curriculum,
)


class Command(BaseCommand):
    """Export curriculum prerequisites as JSON, DOT, and PNG."""

    help = "Export prerequisites for one curriculum as JSON + DOT + PNG."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "-c",
            "--curriculum",
            nargs="+",
            dest="curriculum_short_names",
            help="Curriculum short name (single value required for now).",
        )

    def handle(self, *args, **options):
        short_names: list[str] = options.get("curriculum_short_names") or []
        if len(short_names) != 1:
            raise CommandError("Provide exactly one curriculum short name.")

        curriculum = resolve_curriculum(short_names[0])
        output = export_prereq_graph(curriculum)

        self.stdout.write(self.style.SUCCESS(f"JSON: {output.json_path}"))
        self.stdout.write(self.style.SUCCESS(f"JS: {output.js_path}"))
        self.stdout.write(self.style.SUCCESS(f"DOT: {output.dot_path}"))
        self.stdout.write(self.style.SUCCESS(f"PNG: {output.png_path}"))
