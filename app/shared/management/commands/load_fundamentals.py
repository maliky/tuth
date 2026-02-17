"""Load fundamental fixtures (states, academics, people, legacy grades)."""

from __future__ import annotations

from pathlib import Path

from django.core.management import BaseCommand, CommandError, call_command

from app.shared.auth.helpers import ensure_superuser


class Command(BaseCommand):
    """CLI helper to bootstrap a database with core reference data."""

    help = (
        "Load default states, academic structures, people profiles and "
        "legacy grade/registration data."
    )

    def add_arguments(self, parser) -> None:
        """Register options for pointing to the split CSV directory."""
        parser.add_argument(
            "-d",
            "--dir",
            default="./Seed_data/Fundamentals/",
            help="Directory containing the data files.",
        )

        parser.add_argument(
            "--people",
            action="store_true",
            help="load people data.",
        )
        parser.add_argument(
            "--registry",
            action="store_true",
            help="load registry data.",
        )

    def handle(self, *args, **opts) -> None:
        """Run create_states, load fundamentals, people, then grades."""
        csv_dir = Path(opts["dir"]).expanduser().resolve()

        if not csv_dir.is_dir():
            raise CommandError(f"{csv_dir} is not a directory")

        ensure_superuser(self)
        self.stdout.write("-> Creating default states…")
        call_command("create_states")
        self.stdout.write(self.style.SUCCESS("✔ states ready"))
        call_command("load_roles", verbosity=0)

        self.stdout.write("-> Importing fundamentals")
        _import_resources(csv_dir, ["Room", "Course", "CurriCrs", "Semester"])

        if opts["people"]:
            self.stdout.write("-> Importing people")
            call_command("import_student")
            _import_resources(csv_dir, ["Donor", "Staff", "Faculty"])
            call_command("import_students")

        if opts["registry"]:
            self.stdout.write("-> Importing Registry (Grades+Sessions)")
            call_command("import_grades")
            call_command("import_sessions")
        self.stdout.write(self.style.SUCCESS("✔ fundamental data load completed"))


def _import_resources(directory: Path, resources: list[str]) -> None:
    """Delegate a subset of imports to the import_resources command."""
    if not resources:
        return
    call_command(
        "import_resources",
        "-f",
        str(directory),
        resource=resources,
    )
