"""Fast grade importer that bypasses fuzzy lookups and import-export."""

from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Optional

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

from app.academics.ensures import (
    ensure_college as ensure_college_obj,
    ensure_course as ensure_course_obj,
    ensure_curriculum as ensure_curriculum_obj,
    ensure_curriculum_course as ensure_curriculum_course_obj,
    ensure_department as ensure_department_obj,
)
from app.academics.models.college import College
from app.academics.models.course import Course, CurriculumCourse
from app.academics.models.curriculum import Curriculum
from app.academics.models.department import Department
from app.people.models.faculty import Faculty
from app.people.models.student import Student
from app.registry.models.grade import Grade, GradeValue
from app.shared.models import CreditHour
from app.shared.types import (
    DeptCollegeMapT,
    DeptCourseMapT,
    IntIntMapT,
    SectionKeyMapT,
    StrIntMapT,
    ThreeIntOptIntMapT,
    TwoIntIntMapT,
    TwoStrIntMapT,
)
from app.shared.utils import to_int
from app.timetable.ensures import ensure_semester as ensure_semester_obj
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester
from app.timetable.utils import normalize_academic_year


def _norm_course_no(value: str) -> str:
    """Normalize course numbers like '101.0' -> '101'."""
    value = (value or "").strip()
    if value.endswith(".0"):
        value = value[:-2]
    return value


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

        # Preload caches
        students: StrIntMapT = dict(Student.objects.values_list("student_id", "id"))
        semesters: TwoStrIntMapT = {}
        for ay, num, pk in Semester.objects.values_list(
            "academic_year__code", "number", "id"
        ):
            semesters[(ay, num)] = pk
        curricula: StrIntMapT = {
            name.lower(): pk
            for name, pk in Curriculum.objects.values_list("short_name", "id")
        }
        colleges: StrIntMapT = {
            code.lower(): pk for code, pk in College.objects.values_list("code", "id")
        }
        college_objs: dict[int, College] = {}
        departments: DeptCollegeMapT = {}  # (dept_code, college_id) -> id
        department_objs: dict[int, Department] = {}
        courses: DeptCourseMapT = {}  # (dept_id, course_no) -> id
        course_objs: dict[int, Course] = {}
        curriculum_courses: TwoIntIntMapT = {}  # (curriculum_id, course_id) -> id
        curriculum_objs: dict[int, Curriculum] = {}
        sections: SectionKeyMapT = {}  # (sem, curr_course, num, faculty) -> id
        credit_hours_map: IntIntMapT = {
            code: code for code, in CreditHour.objects.values_list("code")
        }
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

        def ensure_college(code_raw: str) -> int:
            code = (code_raw or "DEFT").strip().lower()
            existing = colleges.get(code)
            if existing:
                return existing
            col_obj = ensure_college_obj(code)
            colleges[code] = col_obj.id
            college_objs[col_obj.id] = col_obj
            return col_obj.id

        def ensure_department(dept_code_raw: str, college_id: int) -> int:
            dept_code = (dept_code_raw or "DEFT").strip().upper()
            key = (dept_code, college_id)
            existing = departments.get(key)
            if existing:
                return existing
            college_obj = college_objs.get(college_id)
            if college_obj is None:
                college_obj = College.objects.get(pk=college_id)
                college_objs[college_id] = college_obj
            dept_obj = ensure_department_obj(dept_code, college_obj)
            departments[key] = dept_obj.id
            department_objs[dept_obj.id] = dept_obj
            return dept_obj.id

        def ensure_course(dept_id: int, course_no_raw: str, title: str) -> int:
            course_no = _norm_course_no(course_no_raw)
            key = (dept_id, course_no)
            existing = courses.get(key)
            if existing:
                return existing
            dept_obj = department_objs.get(dept_id)
            if dept_obj is None:
                dept_obj = Department.objects.get(pk=dept_id)
                department_objs[dept_id] = dept_obj
            course_obj = ensure_course_obj(dept_obj, course_no, title=title)
            courses[key] = course_obj.id
            course_objs[course_obj.id] = course_obj
            return course_obj.id

        def ensure_curriculum(name_raw: str, college_id: int) -> int:
            name = (name_raw or "").strip()
            if not name:
                college_obj = college_objs.get(college_id)
                if college_obj is None:
                    college_obj = College.objects.get(pk=college_id)
                    college_objs[college_id] = college_obj
                cur_obj = ensure_curriculum_obj("", college_obj, fuzzy_threshold=1.0)
                curriculum_objs[cur_obj.id] = cur_obj
                return cur_obj.id
            key = name.lower()
            existing = curricula.get(key)
            if existing:
                return existing
            college_obj = college_objs.get(college_id)
            if college_obj is None:
                college_obj = College.objects.get(pk=college_id)
                college_objs[college_id] = college_obj
            cur_obj = ensure_curriculum_obj(name, college_obj, fuzzy_threshold=1.0)
            curricula[key] = cur_obj.id
            curriculum_objs[cur_obj.id] = cur_obj
            return cur_obj.id

        def ensure_curriculum_course(
            curriculum_id: int, course_id: int, credit_code: int
        ) -> int:
            key = (curriculum_id, course_id)
            existing = curriculum_courses.get(key)
            if existing:
                return existing
            credit_id = credit_hours_map.get(credit_code)
            if credit_id is None:
                CreditHour.objects.get_or_create(code=credit_code)
                credit_hours_map[credit_code] = credit_code
            curriculum_obj = curriculum_objs.get(curriculum_id)
            if curriculum_obj is None:
                curriculum_obj = Curriculum.objects.get(pk=curriculum_id)
                curriculum_objs[curriculum_id] = curriculum_obj
            course_obj = course_objs.get(course_id)
            if course_obj is None:
                course_obj = Course.objects.get(pk=course_id)
                course_objs[course_id] = course_obj
            cc_obj = ensure_curriculum_course_obj(
                curriculum=curriculum_obj,
                course=course_obj,
                credit_code=credit_code,
            )
            curriculum_courses[key] = cc_obj.id
            return cc_obj.id

        def ensure_semester(ay_raw: str, sem_raw: str) -> int:
            ay_code = normalize_academic_year(ay_raw) or ""
            sem_no = to_int(sem_raw, default=0)
            key = (ay_code, sem_no)
            existing = semesters.get(key)
            if existing:
                return existing
            sem_obj = ensure_semester_obj(ay_code, sem_no)
            semesters[key] = sem_obj.id
            return sem_obj.id

        def ensure_section(
            semester_id: int, curriculum_course_id: int, number: int, faculty_id: int
        ) -> int:
            key = (semester_id, curriculum_course_id, number, faculty_id)
            existing = sections.get(key)
            if existing:
                return existing
            sec_obj, _ = Section.objects.get_or_create(
                semester_id=semester_id,
                curriculum_course_id=curriculum_course_id,
                number=number,
                faculty_id=faculty_id,
            )
            sections[key] = sec_obj.id
            return sec_obj.id

        def ensure_student(student_id_raw: str) -> int:
            sid = (student_id_raw or "").strip()
            if not sid:
                return int(Student.get_default().pk)
            existing = students.get(sid)
            if existing:
                return existing
            User = get_user_model()
            base_username = f"student_{sid}".lower()
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exists():
                counter += 1
                username = f"{base_username}{counter}"
            user = User.objects.create_user(
                username=username,
                first_name="Student",
                last_name=sid,
            )
            student = Student(
                user=user,
                student_id=sid,
                curriculum=Curriculum.get_default(),
            )
            student.save()
            students[sid] = int(student.pk)
            return int(student.pk)

        rows_to_create: list[Grade] = []
        # Existing grade pairs to avoid duplicates
        existing_pairs = set(Grade.objects.values_list("student_id", "section_id"))

        start_time = time.time()

        with path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for _, row in enumerate(reader, start=1):
                student_pk = ensure_student(row.get("student_id", ""))
                sem_pk = ensure_semester(
                    row.get("academic_year", ""), row.get("semester_no", "")
                )
                college_pk = ensure_college(row.get("college_code", ""))
                dept_pk = ensure_department(row.get("course_dept", ""), college_pk)
                course_pk = ensure_course(
                    dept_pk, row.get("course_no", ""), row.get("course_title", "") or ""
                )
                curriculum_pk = ensure_curriculum(row.get("curriculum", ""), college_pk)
                credit_code = to_int(row.get("credit_hours", ""), default=3)
                curr_course_pk = ensure_curriculum_course(
                    curriculum_pk, course_pk, credit_code
                )
                sec_no = to_int(row.get("section_no", ""), default=0)
                section_pk = ensure_section(
                    sem_pk, curr_course_pk, sec_no, default_faculty_id
                )

                grade_code = (row.get("grade_code") or "").strip().upper()
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
