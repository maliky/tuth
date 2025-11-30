"""Load fundamental fixtures (states, academics, people, legacy grades)."""

from __future__ import annotations

from pathlib import Path

from django.core.management import BaseCommand, CommandError, call_command


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
            default="./Seed_data/Trimed",
            help="Directory containing the split CSV files.",
        )

    def handle(self, *args, **options) -> None:
        """Run create_states, load fundamentals, people, then grades."""
        csv_dir = Path(options["dir"]).expanduser().resolve()
        if not csv_dir.is_dir():
            raise CommandError(f"{csv_dir} is not a directory")

        self.stdout.write("⇒ Creating default states…")
        call_command("create_states")
        self.stdout.write(self.style.SUCCESS("✔ states ready"))

        self.stdout.write("⇒ Importing academic fundamentals (rooms/courses/semesters)…")
        self._import_resources(csv_dir, ["room", "course", "curriculum_course", "semester"])

        self.stdout.write("⇒ Importing people profiles (faculty/donors/students)…")
        self._import_resources(csv_dir, ["faculty", "donor", "student"])

        self.stdout.write("⇒ Importing legacy registrations and grades…")
        self._import_resources(csv_dir, ["legacy_registration", "legacy_grade"])
        self.stdout.write(self.style.SUCCESS("✔ fundamental data load completed"))

    # ------------------------------------------------------------------ helpers

    def _import_resources(self, directory: Path, resources: list[str]) -> None:
        """Delegate a subset of imports to the import_resources command."""
        if not resources:
            return
        call_command(
            "import_resources",
            str(directory),
            resource=resources,
        )
