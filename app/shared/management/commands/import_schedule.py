from __future__ import annotations

import csv
from pathlib import Path

from app.people.models.profile import _ensure_faculty
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from app.academics.admin.widgets import CourseWidget, CollegeWidget
from app.academics.models import College, Course, Curriculum, CurriculumCourse
from app.spaces.models import Room
from app.timetable.admin.widgets import SemesterWidget
from app.timetable.models import Section, Semester


# ./academics/admin/resources.py: class CollegeResource
# ./academics/admin/resources.py: class CourseResource
# ./academics/admin/resources.py: class CurriculumCourseResource
# ./academics/admin/resources.py: class CurriculumResource
# ./academics/admin/resources.py: class PrerequisiteResource
#
# ./academics/admin/widgets.py: class CourseManyWidget
# ./academics/admin/widgets.py:: class CollegeWidget
# ./academics/admin/widgets.py:: class CourseWidget
# ./academics/admin/widgets.py:: class CurriculumWidget

# ./people/admin/resources.py: class RegistrationResource
#
# ./people/admin/resources.py: class StudentResource

# ./spaces/admin/resources.py: class RoomResource
#
# ./spaces/admin/widgets.py: class BuildingWidget

# ./timetable/admin/resources.py: class AcademicYearResource
# ./timetable/admin/resources.py: class SectionResource
# ./timetable/admin/resources.py: class SemesterResource
#
# ./timetable/admin/widgets.py: class AcademicYearWidget
# ./timetable/admin/widgets.py:: class SemesterWidget


# For CourseWidget we should construct something of the format
# "<course_code>_<course_no>-<college>" and Course Widget will take care for the creation for course and college


class Command(BaseCommand):
    """Import schedule, creating colleges, courses, semesters, sections, faculty, and curricula."""

    help = "Load schedule CSV data into the database."

    def add_arguments(self, parser):
        parser.add_argument("file", type=str, help="Path to schedule CSV")
        parser.add_argument(
            "--dry-run", action="store_true", default=False, help="Validate only"
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        path = Path(opts["file"])
        if not path.exists():
            raise CommandError(f"File not found: {path}")

        dry_run: bool = opts["dry_run"]

        cw = CourseWidget(model=Course, field="code")
        clg_w = CollegeWidget(model=College, field="code")
        sw = SemesterWidget(model=Semester, field="id")

        added_sections = added_curricula = added_curriculum_courses = added_faculty = (
            skipped
        ) = 0

        with path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                try:
                    college = clg_w.clean(row["college"], row)
                    assert college is not None, "college cannot be None"
                    course = cw.clean(f'{row["course_code"]}{row["course_no"]}', row)
                    semester = sw.clean(row["semester"], row)
                    section_no = int(row["section"]) if row["section"].strip() else 1
                    room_id = _ensure_room(row["location"])
                    faculty = _ensure_faculty(row["instructor"], college)
                    curriculum = _ensure_curriculum(row["curriculum"], college)

                    if dry_run:
                        continue

                    section, created = Section.objects.get_or_create(
                        course=course,
                        semester=semester,
                        number=section_no,
                        defaults={
                            "room_id": room_id,
                            "faculty": faculty,
                            "max_seats": 30,
                            "schedule": _human_time(row),
                        },
                    )
                    if created:
                        added_sections += 1

                    # Link course to curriculum
                    cc, cc_created = CurriculumCourse.objects.get_or_create(
                        curriculum=curriculum,
                        course=course,
                    )
                    if cc_created:
                        added_curriculum_courses += 1

                except Exception as exc:
                    skipped += 1
                    self.stderr.write(f"⚠  Skipped row {reader.line_num}: {exc}")

        self.stdout.write(
            self.style.SUCCESS(
                f"{added_sections} sections, {added_faculty} faculty, "
                f"{added_curricula} curricula, {added_curriculum_courses} curriculum-courses added, {skipped} skipped."
            )
        )


def _ensure_room(raw: str) -> int | None:
    if not raw or raw.lower() == "nan":
        return None
    room, _ = Room.objects.get_or_create(name=raw.strip())
    return room.id




def _ensure_curriculum(curriculum_title: str, college: College) -> Curriculum:
    curriculum, created = Curriculum.objects.get_or_create(
        short_name=curriculum_title,
        defaults={"title": curriculum_title, "college": college},
    )
    return curriculum


def _human_time(row: dict[str, str]) -> str:
    weekday = row.get("weekday") or row.get("days")
    if not weekday:
        raise ValueError("Missing 'weekday' or 'days' in row.")
    return f'{weekday[:3]} {row["time_start"]}-{row["time_end"]}'
