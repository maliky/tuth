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
            default="./Seed_data/",
            help="Directory containing the data files.",
        )

    def handle(self, *args, **opts) -> None:
        """Run create_states, load fundamentals, people, then grades."""
        csv_dir = Path(opts["dir"]).expanduser().resolve()

        if not csv_dir.is_dir():
            raise CommandError(f"{csv_dir} is not a directory")

        if not opts["no_seed"]:
            ensure_superuser(self)
            self.stdout.write("-> Creating default states…")
            call_command("create_states")
            self.stdout.write(self.style.SUCCESS("✔ states ready"))
            call_command("load_roles", verbosity=0)

        self.stdout.write("-> Importing fundamentals")
        _import_resources(csv_dir, ["room", "curriculum", "semester"])

        # self.stdout.write("-> Importing people")
        # _import_resources(csv_dir, ["faculty", "donor", "student"])

        # self.stdout.write("-> Importing legacy registrations and grades")
        # _import_resources(csv_dir, ["legacy_registration", "legacy_grade"])

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
