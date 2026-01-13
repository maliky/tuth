"""Reset default passwords for Staff, Faculty, and Student groups."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from app.shared.auth.perms import UserRole

DEFAULT_STAFF_PASSWORD = "PassW0rd!_staff"
DEFAULT_FACULTY_PASSWORD = "PassW0rd!_faculty"
DEFAULT_STUDENT_PASSWORD = "PassW0rd!_student"


def _set_passwords(queryset, password: str) -> int:
    """Set the password for each user in the queryset and return the count."""
    updated = 0
    for user in queryset.iterator():
        user.set_password(password)
        user.save(update_fields=["password"])
        updated += 1
    return updated


class Command(BaseCommand):
    """Reset passwords for group-based user cohorts."""

    help = (
        "Reset passwords for Staff (excluding Faculty), Faculty, and Student groups. "
        "Defaults: PassW0rd!_staff / PassW0rd!_faculty / PassW0rd!_student."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--staff-password",
            default=DEFAULT_STAFF_PASSWORD,
            help="Password for Staff users (excluding Faculty).",
        )
        parser.add_argument(
            "--faculty-password",
            default=DEFAULT_FACULTY_PASSWORD,
            help="Password for Faculty users.",
        )
        parser.add_argument(
            "--student-password",
            default=DEFAULT_STUDENT_PASSWORD,
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

        with transaction.atomic():
            staff_updated = _set_passwords(staff_users, staff_password)
            faculty_updated = _set_passwords(faculty_users, faculty_password)
            student_updated = _set_passwords(student_users, student_password)

        self.stdout.write(
            self.style.SUCCESS(
                "Passwords updated: "
                f"Staff={staff_updated}, Faculty={faculty_updated}, Student={student_updated}."
            )
        )
