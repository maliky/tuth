"""Reset default passwords for Staff, Faculty, and Student groups."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction

from app.shared.auth.perms import UserRole

DEFAULT_STAFF_PASSWORD = "PassW0rd!_staff"
DEFAULT_FACULTY_PASSWORD = "PassW0rd!_faculty"
DEFAULT_STUDENT_PASSWORD = "PassW0rd!_student"


def _set_passwords(queryset, password: str) -> int:
    """Set the password for each user in the queryset and return the count."""
    # Bulk update uses a single hash value for all rows in this cohort.
    hashed_password = make_password(password)
    updated = int(queryset.update(password=hashed_password))
    return updated


class Command(BaseCommand):
    """Reset passwords for Staff, Faculty, and Student groups in bulk."""

    help = (
        "Reset passwords for Staff (excluding Faculty), Faculty, and Student groups "
        "using a bulk update. Pass -t/-f/-s to target specific cohorts; omitted "
        "passwords leave that group unchanged."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "-t",
            "--staff-password",
            default="",
            help="Password for Staff users (excluding Faculty).",
        )
        parser.add_argument(
            "-f",
            "--faculty-password",
            default="",
            help="Password for Faculty users.",
        )
        parser.add_argument(
            "-s",
            "--student-password",
            default="",
            help="Password for Student users.",
        )

    def handle(self, *args, **options):
        staff_password: str = options["staff_password"]
        faculty_password: str = options["faculty_password"]
        student_password: str = options["student_password"]

        User = get_user_model()
        staff_group = UserRole.STAFF.value.group
        faculty_group = UserRole.FACULTY.value.group
        student_group = UserRole.STUDENT.value.group

        # Exclude faculty-group users from the staff cohort.
        staff_users = (
            User.objects.filter(groups=staff_group)
            .exclude(groups=faculty_group)
            .distinct()
        )
        faculty_users = User.objects.filter(groups=faculty_group).distinct()
        student_users = User.objects.filter(groups=student_group).distinct()

        staff_updated = 0
        faculty_updated = 0
        student_updated = 0

        with transaction.atomic():
            if staff_password:
                staff_updated = _set_passwords(staff_users, staff_password)
            if faculty_password:
                faculty_updated = _set_passwords(faculty_users, faculty_password)
            if student_password:
                student_updated = _set_passwords(student_users, student_password)

        self.stdout.write(
            self.style.SUCCESS(
                "Passwords updated: "
                f"Staff={staff_updated}, Faculty={faculty_updated}, Student={student_updated}."
            )
        )
