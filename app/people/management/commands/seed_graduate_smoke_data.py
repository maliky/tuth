"""Seed clearly marked graduate smoke-test students and sections."""

from __future__ import annotations

from typing import cast

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

from app.academics.choices import AcademicCareer
from app.academics.models.curriculum import Curriculum
from app.finance.models.invoice import StdSemesterInvoice
from app.finance.models.payment import Payment
from app.finance.models.status_types_methods import Payer, PaymentMethod, PaymentStatus
from app.finance.registration_invoices import ensure_course_invoice_for_registration
from app.people.models.student import Student
from app.people.models.student_curriculum_enrollment import (
    StdCurriEnroll,
    set_primary_std_curri_enroll,
)
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
        parser.add_argument(
            "--other-program",
            default="GRAD-EDUC-CI",
            help="Second graduate curriculum code for cross-college smoke data.",
        )
        parser.add_argument("--apply", action="store_true", help="Persist changes.")

    def handle(self, *args: object, **options: object) -> None:
        """Seed smoke data inside one transaction."""
        semester = _semester_by_code(str(options["semester"]))
        curriculum = _graduate_curriculum(str(options["program"]))
        other_curriculum = _graduate_curriculum(str(options["other_program"]))
        apply_changes = bool(options.get("apply"))
        with transaction.atomic():
            sections = _ensure_sections(curriculum, semester)
            other_sections = (
                sections
                if other_curriculum.id == curriculum.id
                else _ensure_sections(other_curriculum, semester)
            )
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
            _retire_legacy_smoke_student("grad.msgh.smoke.second")
            third_student = _ensure_student(
                username="grad.educ.smoke.second",
                first_name="Graduate",
                last_name="Education",
                curriculum=other_curriculum,
                semester=semester,
            )
            grades = _ensure_second_year_history(second_student, sections)
            cleared_payments = _clear_student_history_finance(second_student, sections)
            other_grades = _ensure_second_year_history(third_student, other_sections)
            if not apply_changes:
                transaction.set_rollback(True)
        mode = "applied" if apply_changes else "dry-run"
        self.stdout.write(
            self.style.SUCCESS(
                f"graduate smoke seed {mode}: sections={len(sections) + len(other_sections)} "
                f"students=3 grades={grades + other_grades} "
                f"cleared_payments={cleared_payments}"
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
    enroll = set_primary_std_curri_enroll(
        student,
        curriculum,
        entry_semester_id=student.entry_semester_id,
        is_active=True,
    )
    StdCurriEnroll.objects.filter(student=student, is_active=True).exclude(
        pk=enroll.pk
    ).update(is_active=False)
    return cast(Student, student)


def _retire_legacy_smoke_student(username: str) -> None:
    """Delete obsolete smoke-only student data from earlier seed versions."""
    user = User.objects.filter(username=username).first()
    if user is None:
        return
    student = Student.objects.filter(user=user).first()
    if student is None:
        user.delete()
        return
    if SMOKE_MARKER not in student.bio:
        raise CommandError(f"Refusing to delete non-smoke student: {username}")
    user.delete()


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


def _clear_student_history_finance(student: Student, sections: list[Section]) -> int:
    """Create cleared finance rows for completed graduate smoke registrations."""
    Payer._populate_attributes_and_db()
    PaymentMethod._populate_attributes_and_db()
    PaymentStatus._populate_attributes_and_db()
    pending_status = RegistrationStatus.pending()
    cleared_status = RegistrationStatus.cleared()
    section_ids = [
        section.id
        for section in sections
        if int(section.curriculum_course.level_number or 0) <= 2
    ]
    registrations = list(
        Registration.objects.filter(
            student=student,
            section_id__in=section_ids,
        ).select_related("section", "section__curriculum_course", "section__semester")
    )
    parent_ids: set[int] = set()
    for registration in registrations:
        # Completed smoke history needs invoice materialization before clearance.
        Registration.objects.filter(pk=registration.pk).update(status=pending_status)
        registration.status = pending_status
        invoice, _created, _updated = ensure_course_invoice_for_registration(registration)
        if invoice is None:
            Registration.objects.filter(pk=registration.pk).update(status=cleared_status)
            continue
        if invoice.student_semester_invoice_id is not None:
            parent_ids.add(invoice.student_semester_invoice_id)
    cleared_payments = 0
    parent_invoices = StdSemesterInvoice.objects.filter(pk__in=parent_ids)
    for parent_invoice in parent_invoices:
        parent_invoice.refresh_totals_from_sources(save_model=True)
        balance = parent_invoice.get_balance()
        if balance <= 0:
            continue
        payment = (
            Payment.objects.filter(student_semester_invoice=parent_invoice)
            .order_by("id")
            .first()
        )
        if payment is None:
            payment = Payment(student_semester_invoice=parent_invoice)
        payment.amount_paid = balance
        payment.payer_id = "student"
        payment.payment_method = PaymentMethod.get_dft()
        payment.status = PaymentStatus.cleared()
        payment.save()
        parent_invoice.refresh_totals_from_sources(save_model=True)
        cleared_payments += 1
    Registration.objects.filter(
        student=student,
        section_id__in=section_ids,
    ).update(status=cleared_status)
    return cleared_payments


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
