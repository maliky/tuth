"""Fast grade importer that bypasses fuzzy lookups and import-export."""

from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Mapping, TypeAlias

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

from app.academics.ensures import (
    ensure_college_id,
    ensure_crs_id,
    ensure_curri_crs_id,
    ensure_curri_id,
    ensure_dpt_id,
)
from app.people.ensures import ensure_std_sid
from app.people.models.faculty import Faculty
from app.registry.grade_import_errors import write_grade_error_log
from app.registry.grade_registration_reconciliation import (
    GradeRegistrationPairT,
    GradeRegistrationSummary,
    ensure_grade_registration_pairs,
)
from app.registry.models.grade import Grade, GradeValue
from app.shared.types import StrIntMapT
from app.shared.utils import get_in_row, to_int
from app.timetable.ensures import ensure_sec_id, ensure_sem_id

RowT: TypeAlias = Mapping[str, str]


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
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse/import without committing grade rows.",
        )
        parser.add_argument(
            "--max-errors",
            type=int,
            default=25,
            help="Stop after this many row errors.",
        )
        parser.add_argument(
            "--no-reconstruct-registrations",
            action="store_true",
            help="Do not create missing cleared registrations from grade rows.",
        )

    def handle(self, *args, **options):
        path = Path(options["file"])
        if not path.exists():
            raise CommandError(f"Missing file: {path}")

        batch_size: int = options["batch_size"]
        dry_run = bool(options.get("dry_run"))
        max_errors = int(options.get("max_errors") or 25)
        reconstruct_registrations = not bool(options.get("no_reconstruct_registrations"))

        # Caches are preloaded on-demand inside ensure_* helpers.
        grade_values: StrIntMapT = {
            code.lower(): pk for code, pk in GradeValue.objects.values_list("code", "id")
        }

        default_faculty = Faculty.get_dft()
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
        registration_pairs_to_ensure: list[GradeRegistrationPairT] = []
        registration_pairs_seen: set[GradeRegistrationPairT] = set()
        registration_summary = GradeRegistrationSummary()
        # Existing grade pairs to avoid duplicates
        existing_pairs = set(Grade.objects.values_list("student_id", "section_id"))
        error_rows: list[tuple[int, str, RowT]] = []

        start_time = time.time()

        # > at this level we expect all all students in the grade table are already created.
        with transaction.atomic():
            with path.open(newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f, delimiter="\t")
                for row_number, row in enumerate(reader, start=1):
                    try:
                        grade = _grade_from_row(
                            row,
                            grade_values=grade_values,
                            default_faculty_id=default_faculty_id,
                        )
                    except UnknownGradeCodeError:
                        skipped += 1
                        rows_processed += 1
                        continue
                    except Exception as exc:
                        error_rows.append((row_number, str(exc), row))
                        if len(error_rows) >= max_errors:
                            write_grade_error_log(error_rows)
                            raise CommandError(
                                f"Grade import stopped after {len(error_rows)} errors."
                            ) from exc
                        rows_processed += 1
                        continue

                    if reconstruct_registrations:
                        _queue_registration_pair(
                            grade,
                            pairs_to_ensure=registration_pairs_to_ensure,
                            seen_pairs=registration_pairs_seen,
                        )
                    pair = (grade.student_id, grade.section_id)
                    if pair in existing_pairs:
                        rows_processed += 1
                        continue
                    existing_pairs.add(pair)
                    rows_to_create.append(grade)

                    if len(rows_to_create) >= batch_size:
                        Grade.objects.bulk_create(
                            rows_to_create, ignore_conflicts=True, batch_size=batch_size
                        )
                        registration_summary.add(
                            _flush_registration_pairs(
                                registration_pairs_to_ensure,
                                batch_size=batch_size,
                                dry_run=dry_run,
                            )
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
                Grade.objects.bulk_create(
                    rows_to_create, ignore_conflicts=True, batch_size=batch_size
                )
                created_grades_total += len(rows_to_create)

            registration_summary.add(
                _flush_registration_pairs(
                    registration_pairs_to_ensure,
                    batch_size=batch_size,
                    dry_run=dry_run,
                )
            )

            if error_rows:
                write_grade_error_log(error_rows)
                raise CommandError(
                    f"Grade import failed with {len(error_rows)} row errors."
                )

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(
            self.style.SUCCESS(
                f"Grade import complete{' (dry-run)' if dry_run else ''}: "
                f"{created_grades_total} grades created, {skipped} skipped "
                "(missing grade_value or invalid). "
                f"Grade-backed registrations: {registration_summary.created} created, "
                f"{registration_summary.would_create} would-create, "
                f"{registration_summary.existing} existing."
            )
        )


class UnknownGradeCodeError(ValueError):
    """Raised when a source row carries a grade code missing from GradeValue."""


def _grade_from_row(
    row: RowT, *, grade_values: StrIntMapT, default_faculty_id: int
) -> Grade:
    """Build a Grade object from one normalized import row."""
    # > this ensure_student should student manager to find existing student with sid
    student_pk = ensure_std_sid(get_in_row("student_id", row))
    semester_no = get_in_row("semester_no", row) or get_in_row("semester", row)
    sem_pk = ensure_sem_id(get_in_row("academic_year", row), semester_no)
    college_pk = ensure_college_id(get_in_row("college_code", row))
    dept_pk = ensure_dpt_id(get_in_row("course_dept", row), college_pk)
    course_pk = ensure_crs_id(
        dept_pk,
        get_in_row("course_no", row),
        get_in_row("course_title", row),
    )
    curriculum_pk = ensure_curri_id(
        get_in_row("curriculum", row), college_pk, fuzzy_threshold=1.0
    )
    credit_code = to_int(get_in_row("credit_hours", row), default=3)
    curr_course_pk = ensure_curri_crs_id(curriculum_pk, course_pk, credit_code)
    sec_no = to_int(get_in_row("section_no", row))
    section_pk = ensure_sec_id(sem_pk, curr_course_pk, sec_no, default_faculty_id)

    grade_code = get_in_row("grade_code", row).lower()
    grade_value_id = grade_values.get(grade_code)
    if grade_value_id is None:
        raise UnknownGradeCodeError(grade_code)
    return Grade(student_id=student_pk, section_id=section_pk, value_id=grade_value_id)


def _queue_registration_pair(
    grade: Grade,
    *,
    pairs_to_ensure: list[GradeRegistrationPairT],
    seen_pairs: set[GradeRegistrationPairT],
) -> None:
    """Queue one student/section pair for historical registration repair."""
    pair = (int(grade.student_id), int(grade.section_id))
    if pair in seen_pairs:
        return
    seen_pairs.add(pair)
    pairs_to_ensure.append(pair)


def _flush_registration_pairs(
    pairs_to_ensure: list[GradeRegistrationPairT],
    *,
    batch_size: int,
    dry_run: bool,
) -> GradeRegistrationSummary:
    """Create queued grade-backed registrations and clear the queue."""
    if not pairs_to_ensure:
        return GradeRegistrationSummary()
    summary = ensure_grade_registration_pairs(
        pairs_to_ensure,
        batch_size=batch_size,
        dry_run=dry_run,
    )
    pairs_to_ensure.clear()
    return summary
