"""Seed clearly marked graduate smoke-test students and sections."""

from __future__ import annotations

from typing import cast

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

from app.academics.choices import AcademicCareer
from app.academics.models.curriculum import Curriculum
from app.people.models.student import Student
from app.people.models.student_curriculum_enrollment import set_primary_std_curri_enroll
from app.registry.models.grade import Grade, GradeValue
from app.registry.models.registration import Registration, RegistrationStatus
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester

SMOKE_MARKER = "graduate smoke data"


class Command(BaseCommand):
    """Create pilot graduate sections and smoke-test students."""

    help = "Seed test-scoped graduate data for the first graduate-program smoke run."

    def add_arguments(self, parser: CommandParser) -> None:
        """Register command options."""
        parser.add_argument("--semester", required=True, help="Semester code.")
        parser.add_argument("--program", default="GRAD-MBAM", help="Curriculum code.")
        parser.add_argument("--apply", action="store_true", help="Persist changes.")

    def handle(self, *args: object, **options: object) -> None:
        """Seed smoke data inside one transaction."""
        semester = _semester_by_code(str(options["semester"]))
        curriculum = _graduate_curriculum(str(options["program"]))
        apply_changes = bool(options.get("apply"))
        with transaction.atomic():
            sections = _ensure_sections(curriculum, semester)
            _ensure_student(
                username="grad.mbam.smoke.first",
                first_name="Graduate",
                last_name="First",
                curriculum=curriculum,
                semester=semester,
            )
            second_student = _ensure_student(
                username="grad.mbam.smoke.second",
                first_name="Graduate",
                last_name="Second",
                curriculum=curriculum,
                semester=semester,
            )
            grades = _ensure_second_year_history(second_student, sections)
            if not apply_changes:
                transaction.set_rollback(True)
        mode = "applied" if apply_changes else "dry-run"
        self.stdout.write(
            self.style.SUCCESS(
                f"graduate smoke seed {mode}: sections={len(sections)} "
                f"students=2 grades={grades}"
            )
        )


def _graduate_curriculum(code: str) -> Curriculum:
    """Return an active graduate curriculum by short name."""
    curriculum = (
        Curriculum.objects.filter(
            short_name__iexact=code,
            academic_career=AcademicCareer.GRADUATE,
        )
        .select_related("college")
        .first()
    )
    if curriculum is None:
        raise CommandError(f"Graduate curriculum not found: {code}")
    return curriculum


def _semester_by_code(code: str) -> Semester:
    """Resolve common semester-code spellings."""
    wanted = _norm_sem_code(code)
    for semester in Semester.objects.select_related("academic_year"):
        candidates = {
            _norm_sem_code(str(semester)),
            _norm_sem_code(f"{semester.academic_year.code}-S{semester.number}"),
        }
        if wanted in candidates:
            return semester
    raise CommandError(f"Semester not found: {code}")


def _ensure_sections(curriculum: Curriculum, semester: Semester) -> list[Section]:
    """Ensure one pilot section per graduate curriculum course."""
    sections: list[Section] = []
    curriculum_courses = curriculum.programs.select_related("course").order_by(
        "level_number",
        "course__short_code",
    )
    for curriculum_course in curriculum_courses:
        section, _ = Section.objects.get_or_create(
            semester=semester,
            curriculum_course=curriculum_course,
            number=1,
            defaults={"info": SMOKE_MARKER, "max_seats": 30},
        )
        if SMOKE_MARKER not in section.info:
            section.info = f"{section.info}\n{SMOKE_MARKER}".strip()
            section.save(update_fields=["info"])
        sections.append(section)
    return sections


def _ensure_student(
    *,
    username: str,
    first_name: str,
    last_name: str,
    curriculum: Curriculum,
    semester: Semester,
) -> Student:
    """Create or update one graduate smoke student."""
    user, created = User.objects.get_or_create(
        username=username,
        defaults={"first_name": first_name, "last_name": last_name},
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    student, _ = Student.objects.get_or_create(
        user=user,
        defaults={
            "academic_career": AcademicCareer.GRADUATE,
            "entry_semester": semester,
            "last_enrolled_semester": semester,
            "max_credit_hours": 24,
            "bio": SMOKE_MARKER,
        },
    )
    student.academic_career = AcademicCareer.GRADUATE
    student.entry_semester = student.entry_semester or semester
    student.last_enrolled_semester = semester
    student.max_credit_hours = max(int(student.max_credit_hours or 0), 24)
    if SMOKE_MARKER not in student.bio:
        student.bio = f"{student.bio}\n{SMOKE_MARKER}".strip()
    student.save()
    set_primary_std_curri_enroll(
        student,
        curriculum,
        entry_semester_id=student.entry_semester_id,
        is_active=True,
    )
    return cast(Student, student)


def _ensure_second_year_history(student: Student, sections: list[Section]) -> int:
    """Attach cleared registrations and B grades for first-year sections."""
    GradeValue._populate_attributes_and_db()
    grade_value = GradeValue.objects.get(code="b")
    cleared_status = RegistrationStatus.cleared()
    created = 0
    for section in sections:
        level_number = int(section.curriculum_course.level_number or 0)
        if level_number > 2:
            continue
        Registration.objects.get_or_create(
            student=student,
            section=section,
            defaults={"status": cleared_status},
        )
        grade, was_created = Grade.objects.get_or_create(
            student=student,
            section=section,
            defaults={"value": grade_value, "info": SMOKE_MARKER},
        )
        if not was_created and grade.value_id != grade_value.id:
            grade.value = grade_value
            grade.info = f"{grade.info}\n{SMOKE_MARKER}".strip()
            grade.save(update_fields=["value", "info"])
        created += 1
    return created


def _norm_sem_code(value: str) -> str:
    """Normalize common semester-code spellings for matching."""
    return (
        value.strip()
        .lower()
        .replace("/", "-")
        .replace("_sem", "-s")
        .replace("sem", "s")
        .replace("_", "-")
    )
