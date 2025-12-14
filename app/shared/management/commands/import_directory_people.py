"""Import staff/faculty/students from directory data."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable
from tqdm import tqdm

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError, CommandParser

from app.people.importing.directory import DirectoryRow, load_directory_rows
from app.people.models.faculty import Faculty
from app.people.models.staffs import Staff
from app.people.models.student import Student
from app.people.utils import mk_password, mk_username
from app.shared.importing.loggers import CsvRowLogger
from app.shared.utils import get_in_row

User = get_user_model()


class Command(BaseCommand):
    """Seed staff/faculty/students using directory files."""

    help = "Import people records from Seed_data/Directory files."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "-s",
            "--source",
            action="append",
            default=None,
            help="Path(s) to directory CSV/XLSX files. Defaults to all CSV/XLSX under Seed_data/Directory.",
        )
        parser.add_argument(
            "--role",
            choices=["staff", "faculty", "student", "auto"],
            default="auto",
            help="Role to seed; 'auto' uses email/department hints.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and report without writing to the database.",
        )
        parser.add_argument(
            "--start-row",
            type=int,
            default=1,
            help="Start processing from this 1-based row index in the combined input.",
        )

    def handle(self, *args, **options):
        sources: list[str] = options["source"]
        if not sources:
            directory = Path("Seed_data/Directory")
            sources = [
                str(p)
                for p in directory.iterdir()
                if p.suffix.lower() in {".csv", ".xlsx", ".xls"}
            ]
        role: str = options["role"]
        dry_run: bool = options["dry_run"]

        rows: list[DirectoryRow] = []
        for src in sources:
            path = Path(src)
            if not path.exists():
                raise CommandError(f"Missing source file: {path}")
            self.stdout.write(self.style.NOTICE(f"Loading directory data from {path}"))
            rows.extend(load_directory_rows(path))

        logger = CsvRowLogger(
            "directory_import_invalid.csv",
            (
                "email",
                "first_name",
                "last_name",
                "reason",
            ),
            "Directory import skipped {count} rows; see {path}",
        )

        created = updated = skipped = 0

        start_row: int = options["start_row"]
        for idx, entry in enumerate(
            tqdm(rows, desc="Importing directory", total=len(rows) or None),
            start=1,
        ):
            if idx < start_row:
                continue
            if not entry.first_name or not entry.last_name:
                skipped += 1
                logger.log(
                    {
                        "email": entry.email,
                        "first_name": entry.first_name,
                        "last_name": entry.last_name,
                        "reason": "missing name parts",
                    }
                )
                continue

            target_role = role if role != "auto" else _deduce_role(entry)

            if dry_run:
                continue

            if target_role == "student":
                created_flag = _upsert_student(entry)
            elif target_role == "faculty":
                created_flag = _upsert_faculty(entry)
            else:
                created_flag = _upsert_staff(entry)

            if created_flag:
                created += 1
            else:
                updated += 1

        logger.report(self)
        self.stdout.write(
            self.style.SUCCESS(
                f"Directory import completed: {created} created, {updated} updated, {skipped} skipped."
            )
        )


def _deduce_role(entry: DirectoryRow) -> str:
    """Pick a role based on org unit path and division/email hints."""
    oup = (entry.org_unit_path or "").lower()
    division = (entry.division or "").lower()
    position = (entry.position or "").lower()
    email = entry.email.lower()
    if (
        "students" in oup
        or "student" in division
        or email.endswith(".stud@tubmanu.edu.lr")
    ):
        return "student"
    if "faculty" in oup or "faculty" in division or "professor" in position:
        return "faculty"
    if "staff" in oup:
        return "staff"
    return "staff"


def _build_bio(entry: DirectoryRow) -> str:
    """Compose bio text embedding legacy tags if present."""
    base = "; ".join(tag for tag in entry.bio_tags if tag)
    return base


def _limit(text: str, max_len: int | None) -> str:
    """Trim text to a field max length when provided."""
    if max_len is None:
        return text
    return text[:max_len]


def _upsert_staff(entry: DirectoryRow) -> bool:
    """Create or update a Staff profile."""
    username = mk_username(entry.first_name, entry.last_name, prefix_len=2, unique=True)
    username = _limit(username, User._meta.get_field("username").max_length)
    defaults = {
        "first_name": entry.first_name.capitalize(),
        "last_name": entry.last_name.capitalize(),
        "email": entry.email,
        "position": _limit(
            entry.position or "", Staff._meta.get_field("position").max_length
        ),
        "division": _limit(
            entry.division or "", Staff._meta.get_field("division").max_length
        ),
        "phone_number": entry.phone,
        "bio": _build_bio(entry),
    }
    staff, created = Staff.objects.update_or_create(username=username, defaults=defaults)
    if created:
        staff.user.set_password(mk_password(entry.first_name, entry.last_name))
        staff.user.save(update_fields=["password"])
    return bool(created)


def _upsert_faculty(entry: DirectoryRow) -> bool:
    """Create or update a Faculty (wraps Staff)."""
    # Ensure staff profile first
    staff_username = mk_username(
        entry.first_name, entry.last_name, prefix_len=2, unique=True
    )
    staff_username = _limit(staff_username, User._meta.get_field("username").max_length)
    staff, created_staff = Staff.objects.update_or_create(
        username=staff_username,
        defaults={
            "first_name": entry.first_name.capitalize(),
            "last_name": entry.last_name.capitalize(),
            "email": entry.email,
            "position": _limit(
                entry.position or "", Staff._meta.get_field("position").max_length
            ),
            "division": _limit(
                entry.division or "", Staff._meta.get_field("division").max_length
            ),
            "phone_number": entry.phone,
            "bio": _build_bio(entry),
        },
    )
    if created_staff:
        staff.user.set_password(mk_password(entry.first_name, entry.last_name))
        staff.user.save(update_fields=["password"])
    faculty, created_faculty = Faculty.objects.update_or_create(
        staff_profile=staff,
        defaults={},
    )
    return bool(created_staff or created_faculty)


def _upsert_student(entry: DirectoryRow) -> bool:
    """Create or update a Student profile."""
    username = Student.mk_username(entry.first_name, entry.last_name)
    username = _limit(username, User._meta.get_field("username").max_length)
    defaults = {
        "first_name": entry.first_name.capitalize(),
        "last_name": entry.last_name.capitalize(),
        "email": entry.email,
        "phone_number": entry.phone,
        "bio": _build_bio(entry),
    }
    student, created = Student.objects.update_or_create(
        username=username, defaults=defaults
    )
    if created:
        student.set_password(mk_password(entry.first_name, entry.last_name))
        student.save()
    return bool(created)
