"""Fast student importer using exact lookups and batch operations."""

from __future__ import annotations

import csv
import time
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

from app.academics.ensures import ensure_curriculum, ensure_college
from app.people.models.student import Student
from app.shared.types import StrIntMapT, TwoStrIntMapT
from app.shared.utils import normalize_academic_year
from app.timetable.models.semester import Semester

User = get_user_model()


def _to_int(value: str, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


class Command(BaseCommand):
    """Bulk import students from fundamentals CSV/TSV using exact lookups."""

    help = "Fast student import (defaults: StudentInfo.csv, people_students.csv)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "-f",
            "--file",
            action="append",
            default=None,
            help="Path(s) to CSV/TSV files; defaults to fundamentals StudentInfo and people_students.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=2000,
            help="Number of rows per bulk insert/update batch.",
        )

    def handle(self, *args, **options):
        batch_size: int = options["batch_size"]
        sources: list[str] = options["file"] or [
            "Seed_data/Fundamentals/StudentInfo.csv",
            "Seed_data/Fundamentals/people_students.csv",
        ]

        paths = [Path(p) for p in sources]
        missing = [p for p in paths if not p.exists()]
        if missing:
            raise CommandError(
                f"Missing source files: {', '.join(str(p) for p in missing)}"
            )

        # Preload caches
        students: StrIntMapT = dict(Student.objects.values_list("student_id", "id"))
        semesters: TwoStrIntMapT = {}
        for ay, num, pk in Semester.objects.values_list(
            "academic_year__code", "number", "id"
        ):
            semesters[(ay, num)] = pk

        created = 0
        updated = 0
        skipped = 0
        rows_processed = 0
        batch_commits = 0
        start_time = time.time()

        def ensure_semester(ay_raw: str, sem_raw: str) -> int | None:
            ay_code = normalize_academic_year(ay_raw) or ""
            if not ay_code:
                return None
            sem_no = _to_int(sem_raw, default=0)
            key = (ay_code, sem_no)
            existing = semesters.get(key)
            if existing:
                return existing
            sem_obj, _ = Semester.objects.get_or_create(
                academic_year__code=ay_code, number=sem_no
            )
            semesters[key] = sem_obj.id
            return sem_obj.id

        def ensure_user(username: str, first_name: str, last_name: str):
            name_first = (first_name or "Student").strip()
            name_last = (last_name or "").strip()
            base = username or f"student_{name_last or 'unknown'}"
            uname = base
            counter = 1
            while User.objects.filter(username=uname).exists():
                counter += 1
                uname = f"{base}{counter}"
            return User.objects.create_user(
                username=uname,
                first_name=name_first,
                last_name=name_last,
            )

        rows_new: list[Student] = []
        rows_update: list[Student] = []

        def flush_batch():
            nonlocal created, updated, batch_commits, rows_new, rows_update
            if rows_new:
                with transaction.atomic():
                    Student.objects.bulk_create(
                        rows_new, ignore_conflicts=True, batch_size=batch_size
                    )
                created += len(rows_new)
                rows_new.clear()
            if rows_update:
                with transaction.atomic():
                    Student.objects.bulk_update(
                        rows_update,
                        ["curriculum", "entry_semester", "current_enrolled_semester"],
                        batch_size=batch_size,
                    )
                updated += len(rows_update)
                rows_update.clear()
            batch_commits += 1
            if batch_commits % 5 == 0:
                elapsed = time.time() - start_time
                rate = rows_processed / elapsed if elapsed else 0
                self.stdout.write(
                    f"Progress: {rows_processed} rows in {elapsed:.1f}s ({rate:.0f} rows/s)"
                )

        for path in paths:
            with path.open(newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rows_processed += 1
                    student_id = (
                        row.get("student_id") or row.get("StudentID") or ""
                    ).strip()
                    if not student_id:
                        skipped += 1
                        continue
                    first = (
                        row.get("student_first_name") or row.get("First Name") or ""
                    ).strip()
                    last = (
                        row.get("student_last_name") or row.get("Last Name") or student_id
                    ).strip()
                    username = (row.get("username") or "").strip()
                    curriculum_raw = row.get("curriculum") or row.get("Curriculum") or ""
                    college_code = row.get("college_code") or row.get("College") or ""
                    entry_sem = (
                        row.get("entry_semester") or row.get("EntrySemester") or ""
                    )
                    current_sem = (
                        row.get("current_enrolled_sem")
                        or row.get("CurrentSemester")
                        or ""
                    )

                    # Resolve curriculum/college/semesters
                    curr_college = ensure_college(college_code)
                    curriculum = ensure_curriculum(
                        curriculum_raw, curr_college, fuzzy_threshold=1.0
                    )
                    entry_sem_id = ensure_semester(
                        row.get("academic_year", ""), entry_sem
                    )
                    current_sem_id = ensure_semester(
                        row.get("academic_year", ""), current_sem
                    )

                    if student_id in students:
                        student = Student.objects.filter(pk=students[student_id]).first()
                        if student:
                            updated_fields = False
                            if student.curriculum_id != curriculum.id:
                                student.curriculum_id = curriculum.id
                                updated_fields = True
                            if entry_sem_id and student.entry_semester_id != entry_sem_id:
                                student.entry_semester_id = entry_sem_id
                                updated_fields = True
                            if (
                                current_sem_id
                                and student.current_enrolled_semester_id != current_sem_id
                            ):
                                student.current_enrolled_semester_id = current_sem_id
                                updated_fields = True
                            if updated_fields:
                                rows_update.append(student)
                        continue

                    user = ensure_user(username, first, last)
                    student = Student(
                        user=user,
                        student_id=student_id,
                        curriculum=curriculum,
                        entry_semester_id=entry_sem_id,
                        current_enrolled_semester_id=current_sem_id,
                    )
                    rows_new.append(student)
                    students[student_id] = 0  # mark as seen

                    if len(rows_new) + len(rows_update) >= batch_size:
                        flush_batch()

        flush_batch()

        self.stdout.write(
            self.style.SUCCESS(
                f"Student import complete: {created} created, {updated} updated, {skipped} skipped."
            )
        )
