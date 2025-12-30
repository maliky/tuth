"""Fast student importer using exact lookups and batch operations."""

from __future__ import annotations

import csv
import time
from datetime import datetime, date
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

from app.academics.ensures import ensure_curriculum, ensure_college
from app.people.models.student import Student
from app.shared.utils import normalize_academic_year
from app.timetable.ensures import ensure_semester
from app.timetable.models.semester import Semester

UserModel = get_user_model()


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
            "Seed_data/Fundamentals/people_students.csv",
            "Seed_data/Fundamentals/StudentInfo.csv",
        ]

        paths = [Path(p) for p in sources]
        missing = [p for p in source if not Path(p).exists()]
        if missing:
            raise CommandError(
                f"Missing source files: {', '.join(missing)}"
            )

        # Preload caches
        existing_students = {
            s.student_id: s for s in Student.objects.select_related("user").all()
        }
        semesters: dict[tuple[str, int], int] = {}
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

        def _fetch_semester_id(ay_raw: str, sem_raw: str) -> int | None:
            ay_code = normalize_academic_year(ay_raw) or ""
            if not ay_code:
                return None
            sem_no = _to_int(sem_raw, default=0)
            key = (ay_code, sem_no)
            existing = semesters.get(key)
            if existing:
                return existing
            sem_obj = ensure_semester(ay_code, sem_no)
            semesters[key] = sem_obj.id
            return sem_obj.id

        def ensure_user(username: str, first_name: str, last_name: str) -> User:
            name_first = (first_name or "Student").strip()
            name_last = (last_name or "").strip()
            base = username or Student.mk_username(
                name_first, name_last, prefix_len=3, unique=False
            )
            uname = base
            counter = 1
            while UserModel.objects.filter(username=uname).exists():
                counter += 1
                uname = f"{base}{counter}"
            return UserModel.objects.create_user(
                username=uname,
                first_name=name_first,
                last_name=name_last,
            )

        rows_new: list[Student] = []
        rows_update: list[Student] = []
        pending_new: dict[str, Student] = {}
        pending_existing: dict[str, Student] = {}

        def _parse_birth_date(raw: str | None) -> date | None:
            if not raw:
                return None
            text = str(raw).strip()
            for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y"):
                try:
                    return datetime.strptime(text, fmt).date()
                except ValueError:
                    continue
            return None

        def _normalize_gender(raw: str | None) -> str:
            token = (raw or "").strip().lower()
            mapping = {"m": "m", "male": "m", "f": "f", "female": "f"}
            return mapping.get(token, "")

        def _merge_student_fields(student: Student, row: dict[str, str]) -> bool:
            """Merge incoming row data into an existing Student; return True when mutated."""
            mutated = False
            # Semesters and curriculum
            entry_sem_id = _fetch_semester_id(
                row.get("academic_year", ""), row.get("entry_semester", "")
            )
            current_sem_id = _fetch_semester_id(
                row.get("academic_year", ""), row.get("current_enrolled_sem", "")
            )
            curriculum_raw = row.get("curriculum") or row.get("Curriculum") or ""
            college_code = row.get("college_code") or row.get("College") or ""
            curriculum = ensure_curriculum(
                curriculum_raw, ensure_college(college_code), fuzzy_threshold=1.0
            )

            if student.curriculum_id != curriculum.id:
                student.curriculum = curriculum
                mutated = True
            if entry_sem_id and student.entry_semester_id != entry_sem_id:
                student.entry_semester_id = entry_sem_id
                mutated = True
            if current_sem_id and student.current_enrolled_semester_id != current_sem_id:
                student.current_enrolled_semester_id = current_sem_id
                mutated = True

            # Personal details (only fill when provided)
            id_value = (row.get("student_id") or row.get("StudentID") or "").strip()
            first_name_raw = (
                row.get("student_first_name") or row.get("First Name") or ""
            ).strip()
            last_name_raw = (
                row.get("student_last_name") or row.get("Last Name") or ""
            ).strip()
            if not getattr(student, "user_id", None):
                student.user = ensure_user(
                    row.get("username") or "",
                    first_name_raw,
                    last_name_raw or id_value,
                )
                mutated = True
            if row.get("student_first_name") or row.get("First Name"):
                first = first_name_raw
                if student.user_id and student.user.first_name != first and first:
                    student.user.first_name = first
                    student.user.save(update_fields=["first_name"])
            if row.get("student_last_name") or row.get("Last Name"):
                last = last_name_raw
                if student.user_id and student.user.last_name != last and last:
                    student.user.last_name = last
                    student.user.save(update_fields=["last_name"])

            middle_name = (row.get("Middle Name") or row.get("middle_name") or "").strip()
            prefix = (row.get("name_prefix") or "").strip()
            suffix = (row.get("name_suffix") or "").strip()
            birth_place = (row.get("birth_place") or "").strip()
            phone_number = (row.get("phone_number") or row.get("phone_no") or "").strip()
            physical_address = (
                row.get("physical_address") or row.get("address") or ""
            ).strip()
            nationality = (row.get("nationality") or "").strip()
            origin_county = (row.get("origin_county") or "").strip()
            bio = (row.get("bio") or "").strip()
            reason_for_leaving = (row.get("reason_for_leaving") or "").strip()
            last_school_attended = (row.get("last_school_attended") or "").strip()
            father_name = (row.get("father_name") or "").strip()
            father_address = (row.get("father_address") or "").strip()
            mother_name = (row.get("mother_name") or "").strip()
            mother_address = (row.get("mother_address") or "").strip()
            emergency_contact = (row.get("emergency_contact") or "").strip()
            birth_date = _parse_birth_date(row.get("birth_date"))
            gender_val = _normalize_gender(row.get("gender"))

            for field_name, val in (
                ("middle_name", middle_name),
                ("name_prefix", prefix),
                ("name_suffix", suffix),
                ("birth_place", birth_place),
                ("birth_date", birth_date),
                ("phone_number", phone_number),
                ("physical_address", physical_address),
                ("nationality", nationality),
                ("origin_county", origin_county),
                ("bio", bio),
                ("reason_for_leaving", reason_for_leaving),
                ("last_school_attended", last_school_attended),
                ("father_name", father_name),
                ("father_address", father_address),
                ("mother_name", mother_name),
                ("mother_address", mother_address),
                ("emergency_contact", emergency_contact),
                ("gender", gender_val),
            ):
                before = getattr(student, field_name, None)
                if val and before != val:
                    setattr(student, field_name, val)
                    mutated = True

            return mutated

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
                        [
                            "user",
                            "curriculum",
                            "entry_semester",
                            "current_enrolled_semester",
                            "middle_name",
                            "name_prefix",
                            "name_suffix",
                            "birth_date",
                            "birth_place",
                            "gender",
                            "phone_number",
                            "physical_address",
                            "nationality",
                            "origin_county",
                            "bio",
                            "reason_for_leaving",
                            "last_school_attended",
                            "father_name",
                            "father_address",
                            "mother_name",
                            "mother_address",
                            "emergency_contact",
                        ],
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
                    if student_id in pending_new:
                        student = pending_new[student_id]
                        if _merge_student_fields(student, row):
                            rows_update.append(student)
                        continue
                    if student_id in pending_existing:
                        student = pending_existing[student_id]
                        if _merge_student_fields(student, row):
                            rows_update.append(student)
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

                    curr_college = ensure_college(college_code)
                    curriculum = ensure_curriculum(
                        curriculum_raw, curr_college, fuzzy_threshold=1.0
                    )
                    entry_sem_id = _fetch_semester_id(
                        row.get("academic_year", ""), entry_sem
                    )
                    current_sem_id = _fetch_semester_id(
                        row.get("academic_year", ""), current_sem
                    )

                    existing_student = existing_students.get(student_id)
                    if existing_student:
                        pending_existing[student_id] = existing_student
                        if _merge_student_fields(existing_student, row):
                            rows_update.append(existing_student)
                        continue

                    user = ensure_user(username, first, last)
                    student = Student(
                        user=user,
                        student_id=student_id,
                        curriculum=curriculum,
                        entry_semester_id=entry_sem_id,
                        current_enrolled_semester_id=current_sem_id,
                        middle_name=(
                            row.get("Middle Name") or row.get("middle_name") or ""
                        ).strip(),
                        name_prefix=(row.get("name_prefix") or "").strip(),
                        name_suffix=(row.get("name_suffix") or "").strip(),
                        birth_date=_parse_birth_date(row.get("birth_date")),
                        gender=_normalize_gender(row.get("gender")),
                        phone_number=(
                            row.get("phone_number") or row.get("phone_no") or ""
                        ).strip(),
                        physical_address=(
                            row.get("physical_address") or row.get("address") or ""
                        ).strip(),
                        nationality=(row.get("nationality") or "").strip(),
                        origin_county=(row.get("origin_county") or "").strip(),
                        bio=(row.get("bio") or "").strip(),
                        reason_for_leaving=(row.get("reason_for_leaving") or "").strip(),
                        last_school_attended=(
                            row.get("last_school_attended") or ""
                        ).strip(),
                        father_name=(row.get("father_name") or "").strip(),
                        father_address=(row.get("father_address") or "").strip(),
                        mother_name=(row.get("mother_name") or "").strip(),
                        mother_address=(row.get("mother_address") or "").strip(),
                        emergency_contact=(row.get("emergency_contact") or "").strip(),
                    )
                    rows_new.append(student)
                    pending_new[student_id] = student
                    existing_students[student_id] = student

                    if len(rows_new) + len(rows_update) >= batch_size:
                        flush_batch()

        flush_batch()

        self.stdout.write(
            self.style.SUCCESS(
                f"Student import complete: {created} created, {updated} updated, {skipped} skipped."
            )
        )
