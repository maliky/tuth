"""Create or refresh launch graduate semesters."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from app.timetable.graduate_calendar import ensure_graduate_semesters


class Command(BaseCommand):
    """Ensure graduate launch semesters exist with the intended windows."""

    help = "Create or update the graduate semesters for academic years 26-27 and 27-28."

    def handle(self, *args, **options) -> None:
        """Run the graduate semester seed operation."""
        for semester, created in ensure_graduate_semesters():
            action = "created" if created else "updated"
            self.stdout.write(
                self.style.SUCCESS(
                    f"{action} {semester} {semester.start_date} "
                    f"{semester.end_date} {semester.status_id}"
                )
            )
