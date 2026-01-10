"""Fast grade importer that bypasses fuzzy lookups and import-export."""

from __future__ import annotations

import csv
import time
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

from app.academics.ensures import (
    ensure_college_id,
    ensure_course_id,
    ensure_curriculum_course_id,
    ensure_curriculum_id,
    ensure_department_id,
)
from app.people.ensures import ensure_student_sid
from app.people.models.faculty import Faculty
from app.registry.models.grade import Grade, GradeValue
from app.shared.types import StrIntMapT
from app.shared.utils import get_in_row, to_int
from app.timetable.ensures import ensure_section_id, ensure_semester_id


class Command(BaseCommand):
    """Bulk import grades quickly using exact lookups and caching."""

    help = "Fast grade import (TSV expected)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "-f",
            "--file",
            default="Seed_data/Fundamentals/full_grades.tsv",
            help="Path to TSV file containing grades.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=5000,
            help="Number of rows per bulk insert chunk.",
        )

    def handle(self, *args, **options):
        path = Path(options["file"])
        if not path.exists():
            raise CommandError(f"Missing file: {path}")

        batch_size: int = options["batch_size"]

        # Caches are preloaded on-demand inside ensure_* helpers.
        grade_values: StrIntMapT = {
            code.upper(): pk for code, pk in GradeValue.objects.values_list("code", "id")
        }

        default_faculty = Faculty.get_default()
        default_faculty_id = default_faculty.id

        created_grades_total = 0
        skipped = 0
        rows_processed = 0
        batch_commits = 0

        # Increase CSV field size limit to avoid errors
        try:
            csv.field_size_limit(10_000_000)
        except Exception:
            pass

        rows_to_create: list[Grade] = []
        # Existing grade pairs to avoid duplicates
        existing_pairs = set(Grade.objects.values_list("student_id", "section_id"))

        start_time = time.time()

        # > at this level we expect all all students in the grade table are already created.
        with path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for _, row in enumerate(reader, start=1):
                # > this ensure_student should student manager to find existing student with sid
                student_pk = ensure_student_sid(get_in_row("student_id", row))

                # Looking for the section
                sem_pk = ensure_semester_id(
                    get_in_row("academic_year", row), get_in_row("semester_no", row)
                )
                college_pk = ensure_college_id(get_in_row("college_code", row))
                dept_pk = ensure_department_id(get_in_row("course_dept", row), college_pk)
                course_pk = ensure_course_id(
                    dept_pk, get_in_row("course_no", row), get_in_row("course_title", row)
                )
                curriculum_pk = ensure_curriculum_id(
                    get_in_row("curriculum", row), college_pk, fuzzy_threshold=1.0
                )
                credit_code = to_int(get_in_row("credit_hours", row), default=3)
                curr_course_pk = ensure_curriculum_course_id(
                    curriculum_pk, course_pk, credit_code
                )
                sec_no = to_int(get_in_row("section_no", row))
                section_pk = ensure_section_id(
                    sem_pk, curr_course_pk, sec_no, default_faculty_id
                )

                # Looking for the grade
                grade_code = get_in_row("grade_code", row).upper()
                grade_value_id = grade_values.get(grade_code)
                if grade_value_id is None:
                    skipped += 1
                    continue

                pair = (student_pk, section_pk)
                if pair in existing_pairs:
                    continue
                existing_pairs.add(pair)

                rows_to_create.append(
                    Grade(
                        student_id=student_pk,
                        section_id=section_pk,
                        value_id=grade_value_id,
                    )
                )

                if len(rows_to_create) >= batch_size:
                    with transaction.atomic():
                        Grade.objects.bulk_create(
                            rows_to_create, ignore_conflicts=True, batch_size=batch_size
                        )
                    created_grades_total += len(rows_to_create)
                    rows_to_create.clear()
                    batch_commits += 1
                    if batch_commits % 5 == 0:
                        elapsed = time.time() - start_time
                        rate = rows_processed / elapsed if elapsed else 0
                        self.stdout.write(
                            f"Progress: {rows_processed} rows in {elapsed:.1f}s ({rate:.0f} rows/s)"
                        )

                rows_processed += 1

        if rows_to_create:
            with transaction.atomic():
                Grade.objects.bulk_create(
                    rows_to_create, ignore_conflicts=True, batch_size=batch_size
                )
            created_grades_total += len(rows_to_create)

        self.stdout.write(
            self.style.SUCCESS(
                f"Grade import complete: {created_grades_total} grades created, {skipped} skipped (missing grade_value or invalid)."
            )
        )
