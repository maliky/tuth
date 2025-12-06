"""Import staff/faculty/students from directory data."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from django.core.management.base import BaseCommand, CommandError, CommandParser

from app.people.importing.directory import DirectoryRow, load_directory_rows
from app.people.models.faculty import Faculty
from app.people.models.staffs import Staff
from app.people.models.student import Student
from app.people.utils import mk_password, mk_username
from app.shared.importing.loggers import CsvRowLogger
from app.shared.utils import get_in_row


class Command(BaseCommand):
    """Seed staff/faculty/students using directory files."""

    help = "Import people records from Seed_data/Directory files."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "-s",
            "--source",
            action="append",
            default=["Seed_data/Directory/google_users_admin_export_250311.csv"],
            help="Path(s) to directory CSV/XLSX files.",
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

    def handle(self, *args, **options):
        sources: list[str] = options["source"]
        role: str = options["role"]
        dry_run: bool = options["dry_run"]

        rows: list[DirectoryRow] = []
        for src in sources:
            path = Path(src)
            if not path.exists():
                raise CommandError(f"Missing source file: {path}")
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

        for entry in rows:
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

            target_role = role
            if role == "auto":
                # heuristic: students have @stud in email, staff otherwise
                if entry.email.endswith(".stud@tubmanu.edu.lr") or "student" in entry.division.lower():
                    target_role = "student"
                else:
                    target_role = "staff"

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


def _build_bio(entry: DirectoryRow) -> str:
    """Compose bio text embedding legacy tags if present."""
    base = "; ".join(tag for tag in entry.bio_tags if tag)
    return base


def _upsert_staff(entry: DirectoryRow) -> bool:
    """Create or update a Staff profile."""
    username = mk_username(entry.first_name, entry.last_name, prefix_len=2, unique=True)
    defaults = {
        "first_name": entry.first_name.capitalize(),
        "last_name": entry.last_name.capitalize(),
        "email": entry.email,
        "position": entry.position or "",
        "division": entry.division or "",
        "phone_number": entry.phone,
        "bio": _build_bio(entry),
    }
    staff, created = Staff.objects.update_or_create(username=username, defaults=defaults)
    if created:
        staff.user.set_password(mk_password(entry.first_name, entry.last_name))
        staff.user.save(update_fields=["password"])
    return created


def _upsert_faculty(entry: DirectoryRow) -> bool:
    """Create or update a Faculty (wraps Staff)."""
    # Ensure staff profile first
    created_staff = _upsert_staff(entry)
    staff_username = mk_username(entry.first_name, entry.last_name, prefix_len=2, unique=True)
    staff = Staff.objects.get(username__iexact=staff_username)
    faculty, created = Faculty.objects.get_or_create(staff_profile=staff)
    return created or created_staff


def _upsert_student(entry: DirectoryRow) -> bool:
    """Create or update a Student profile."""
    username = Student.mk_username(entry.first_name, entry.last_name)
    defaults = {
        "first_name": entry.first_name.capitalize(),
        "last_name": entry.last_name.capitalize(),
        "email": entry.email,
        "phone_number": entry.phone,
        "bio": _build_bio(entry),
    }
    student, created = Student.objects.update_or_create(username=username, defaults=defaults)
    if created:
        student.set_password(mk_password(entry.first_name, entry.last_name))
        student.save(update_fields=["password"])
    return created
