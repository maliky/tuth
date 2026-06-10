"""Operational student, grade, section, and finance snapshot rows."""

from __future__ import annotations

from collections.abc import Iterable

from app.academics.reconciliation_io import RowT, as_cell, course_key
from app.finance.models import CrsInvoice, Payment, StdSemesterInvoice
from app.people.models import Student
from app.people.models.student_curriculum_enrollment import StdCurriEnroll
from app.registry.models import Grade, Registration
from app.timetable.models.section import Section


def _student_label(student: Student) -> str:
    """Return a compact student label for snapshot rows."""
    return as_cell(getattr(student, "student_id", "")) or as_cell(student.id)


def _section_fields(section: Section) -> RowT:
    """Return common Section/CurriculumCourse context."""
    curriculum_course = section.curriculum_course
    course = curriculum_course.course
    return {
        "section_id": as_cell(section.id),
        "semester_id": as_cell(section.semester_id),
        "curriculum_course_id": as_cell(curriculum_course.id),
        "curriculum": as_cell(curriculum_course.curriculum.short_name),
        "course_key": course_key(course.department.code, course.number),
        "course_title": as_cell(course.title),
        "section_number": as_cell(section.number),
    }


def iter_student_curriculum_enrollment_rows() -> Iterable[RowT]:
    """Yield student-curriculum rows that must survive catalog reconciliation."""
    enrollments = StdCurriEnroll.objects.select_related(
        "student__user", "curriculum", "entry_semester", "exit_semester"
    ).order_by("student__student_id", "curriculum__short_name", "id")
    for enrollment in enrollments.iterator():
        yield {
            "student_curriculum_enrollment_id": as_cell(enrollment.id),
            "student_object_id": as_cell(enrollment.student_id),
            "student_id": _student_label(enrollment.student),
            "username": as_cell(enrollment.student.username),
            "curriculum_id": as_cell(enrollment.curriculum_id),
            "curriculum": as_cell(enrollment.curriculum.short_name),
            "entry_semester_id": as_cell(enrollment.entry_semester_id),
            "exit_semester_id": as_cell(enrollment.exit_semester_id),
            "is_primary": as_cell(enrollment.is_primary),
            "is_active": as_cell(enrollment.is_active),
        }


def iter_section_rows() -> Iterable[RowT]:
    """Yield current sections attached to curriculum courses."""
    sections = Section.objects.select_related(
        "semester",
        "curriculum_course__curriculum",
        "curriculum_course__course__department",
    ).order_by("semester_id", "curriculum_course_id", "number", "id")
    for section in sections.iterator():
        row = _section_fields(section)
        row["faculty_id"] = as_cell(section.faculty_id)
        row["current_registrations"] = as_cell(section.current_registrations)
        yield row


def iter_registration_rows() -> Iterable[RowT]:
    """Yield current student registrations with their section/course context."""
    registrations = Registration.objects.select_related(
        "student__user",
        "section__semester",
        "section__curriculum_course__curriculum",
        "section__curriculum_course__course__department",
    ).order_by("student__student_id", "section_id", "id")
    for registration in registrations.iterator():
        row = _section_fields(registration.section)
        row.update(
            {
                "registration_id": as_cell(registration.id),
                "student_object_id": as_cell(registration.student_id),
                "student_id": _student_label(registration.student),
                "username": as_cell(registration.student.username),
                "status": as_cell(registration.status_id),
                "date_registered": as_cell(registration.date_registered),
            }
        )
        yield row


def iter_grade_rows() -> Iterable[RowT]:
    """Yield current grades with immutable section/course context."""
    grades = Grade.objects.select_related(
        "student__user",
        "value",
        "section__semester",
        "section__curriculum_course__curriculum",
        "section__curriculum_course__course__department",
    ).order_by("student__student_id", "section_id", "id")
    for grade in grades.iterator():
        row = _section_fields(grade.section)
        row.update(
            {
                "grade_id": as_cell(grade.id),
                "student_object_id": as_cell(grade.student_id),
                "student_id": _student_label(grade.student),
                "username": as_cell(grade.student.username),
                "grade_value": as_cell(grade.value_id),
                "grade_number": as_cell(grade.number()),
                "is_effective": as_cell(grade.is_effective),
                "graded_on": as_cell(grade.graded_on),
            }
        )
        yield row


def iter_course_invoice_rows() -> Iterable[RowT]:
    """Yield course invoices tied directly to curriculum-course rows."""
    invoices = CrsInvoice.objects.select_related(
        "student__user",
        "semester",
        "student_semester_invoice",
        "curriculum_course__curriculum",
        "curriculum_course__course__department",
    ).order_by("student__student_id", "semester_id", "curriculum_course_id", "id")
    for invoice in invoices.iterator():
        curriculum_course = invoice.curriculum_course
        course = curriculum_course.course
        yield {
            "course_invoice_id": as_cell(invoice.id),
            "student_semester_invoice_id": as_cell(invoice.student_semester_invoice_id),
            "student_object_id": as_cell(invoice.student_id),
            "student_id": _student_label(invoice.student),
            "username": as_cell(invoice.student.username),
            "semester_id": as_cell(invoice.semester_id),
            "curriculum_course_id": as_cell(curriculum_course.id),
            "curriculum": as_cell(curriculum_course.curriculum.short_name),
            "course_key": course_key(course.department.code, course.number),
            "initial_amount_due": as_cell(invoice.initial_amount_due),
            "balance": as_cell(invoice.balance),
            "status": as_cell(invoice.status_id),
        }


def iter_semester_invoice_rows() -> Iterable[RowT]:
    """Yield parent invoices that payments depend on."""
    invoices = StdSemesterInvoice.objects.select_related("student__user", "semester")
    for invoice in invoices.order_by("student__student_id", "semester_id", "id"):
        yield {
            "student_semester_invoice_id": as_cell(invoice.id),
            "student_object_id": as_cell(invoice.student_id),
            "student_id": _student_label(invoice.student),
            "username": as_cell(invoice.student.username),
            "semester_id": as_cell(invoice.semester_id),
            "initial_amount_due": as_cell(invoice.initial_amount_due),
            "required_deposit_amount": as_cell(invoice.required_deposit_amount),
            "balance": as_cell(invoice.balance),
            "status": as_cell(invoice.status_id),
        }


def iter_payment_rows() -> Iterable[RowT]:
    """Yield payment rows linked to parent invoices."""
    payments = Payment.objects.select_related(
        "student_semester_invoice__student__user",
        "student_semester_invoice__semester",
    ).order_by("student_semester_invoice_id", "id")
    for payment in payments.iterator():
        invoice = payment.student_semester_invoice
        yield {
            "payment_id": as_cell(payment.id),
            "student_semester_invoice_id": as_cell(payment.student_semester_invoice_id),
            "student_object_id": as_cell(invoice.student_id),
            "student_id": _student_label(invoice.student),
            "username": as_cell(invoice.student.username),
            "semester_id": as_cell(invoice.semester_id),
            "amount_paid": as_cell(payment.amount_paid),
            "payer": as_cell(payment.payer_id),
            "payment_method": as_cell(payment.payment_method_id),
            "status": as_cell(payment.status_id),
        }
