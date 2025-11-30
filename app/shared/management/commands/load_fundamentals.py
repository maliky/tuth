"""Load fundamental fixtures (states, academics, people, legacy grades)."""

from __future__ import annotations

import csv
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import BaseCommand, CommandError, call_command

from app.people.models.donor import Donor
from app.people.utils import mk_password, split_name

User = get_user_model()


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

        self.stdout.write("⇒ Importing people profiles (faculty/students/donors)…")
        self._import_resources(csv_dir, ["faculty", "student"])
        self._load_donors(csv_dir / "people_donors.csv")

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

    def _load_donors(self, csv_path: Path) -> None:
        """Create Donor profiles from the trimmed donor list."""
        if not csv_path.exists():
            self.stdout.write(
                self.style.WARNING(f"↷ skipping donors: {csv_path.name} missing")
            )
            return

        created = 0
        with csv_path.open(encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                raw_name = (row.get("donors") or "").strip()
                if not raw_name:
                    continue

                prefix, first, middle, last, suffix = split_name(raw_name)
                first = first or raw_name
                last = last or "Donor"
                username = Donor.mk_username(first, last)

                user, user_created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        "first_name": first.capitalize(),
                        "last_name": last.capitalize(),
                    },
                )
                if user_created:
                    user.set_password(mk_password(first, last))
                    user.save(update_fields=["password"])

                donor, was_created = Donor.objects.get_or_create(
                    user=user,
                    defaults={
                        "username": username,
                        "name_prefix": prefix,
                        "middle_name": middle,
                        "name_suffix": suffix,
                    },
                )
                if was_created:
                    created += 1

        msg = f"✔ {created} donors imported" if created else "↷ no donors imported"
        self.stdout.write(self.style.SUCCESS(msg) if created else msg)
