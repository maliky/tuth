"""Test fixtures for the registry app."""

from __future__ import annotations

from decimal import Decimal
from typing import Callable, TypeAlias

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from app.registry.choices import DocumentType, StatusRegistration
from app.registry.models import (
    DocumentStudent,
    DocumentStaff,
    DocumentDonor,
    Grade,
    Registration,
)
from app.registry.models.grade import GradeValue

RegistrationFactory: TypeAlias = Callable[[str, str, str, str, int], Registration]
GradeFactory: TypeAlias = Callable[[str, str, str, str, Decimal], Grade]
DocumentStudentFactory: TypeAlias = Callable[[str, str], DocumentStudent]
DocumentStaffFactory: TypeAlias = Callable[[str, str], DocumentStaff]
DocumentDonorFactory: TypeAlias = Callable[[str, str], DocumentDonor]

DECIMAL_90 = Decimal("90")


@pytest.fixture
def registration(student_factory, section_factory) -> Registration:
    """Default registration for a student."""
    student = student_factory("Regina Stud", "Bsc. REGULAR")
    section = section_factory("007", "Bsc. REGULAR", 1)
    return Registration.objects.create(student=student, section=section)


@pytest.fixture
def grade(student_factory, section_factory) -> Grade:
    """Default grade for a student in a section."""
    student = student_factory("Regina Stud", "Bsc. REGULAR")
    section = section_factory("007", "Bsc. REGULAR", 1)

    grade_value = GradeValue.objects.create(code="A")
    return Grade.objects.create(
        student=student,
        section=section,
        value=grade_value,
    )


@pytest.fixture
def documentStudent(student_factory) -> DocumentStudent:
    """Default document attached to a student."""
    return DocumentStudent.objects.create(
        person=student_factory("Regina Stud", "Bsc. REGULAR"),
        data_file=SimpleUploadedFile("doc.txt", b"data"),
        document_type=DocumentType.WAEC,
    )


@pytest.fixture
def documentDonor(donor_factory) -> DocumentDonor:
    """Default document attached to a student."""
    return DocumentDonor.objects.create(
        person=donor_factory("Generous Donor"),
        data_file=SimpleUploadedFile("doc.txt", b"data"),
        document_type=DocumentType.RECCOM,
    )


@pytest.fixture
def documentStaff(staff_factory) -> DocumentStaff:
    """Default document attached to a student."""
    return DocumentStaff.objects.create(
        person=staff_factory("Stiff Staff"),
        data_file=SimpleUploadedFile("doc.txt", b"data"),
        document_type=DocumentType.APPLET,
    )


# ─── factory fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def registration_factory(student_factory, section_factory) -> RegistrationFactory:
    """Return a callable to build registrations.

    Parameters allow customizing the semester of the created section.
    """

    def _make(
        student_uname: str,
        curri_short_name: str,
        course_number: str,
        status: str = StatusRegistration.PENDING,
        semester_number: int = 1,
    ) -> Registration:
        return Registration.objects.create(
            student=student_factory(student_uname, curri_short_name),
            section=section_factory(course_number, curri_short_name, 1, semester_number),
            status=status,
        )

    return _make


@pytest.fixture
def grade_factory(student_factory, section_factory) -> GradeFactory:
    """Return a callable to build grades."""

    def _make(
        student_uname: str,
        curri_short_name: str,
        course_number: str,
        letter: str = "A",
        numeric: Decimal = DECIMAL_90,
    ) -> Grade:

        grade_value, _ = GradeValue.objects.get_or_create(code=letter)
        return Grade.objects.create(
            student=student_factory(student_uname, curri_short_name),
            section=section_factory(course_number, curri_short_name),
            value=grade_value,
        )

    return _make


@pytest.fixture
def documentstudent_factory(student_factory) -> DocumentStudentFactory:
    """Return a callable to build documents for Students."""

    def _make(student_uname: str, curri_short_name: str) -> DocumentStudent:
        student = student_factory(student_uname, curri_short_name)
        return DocumentStudent.objects.create(
            person=student,
            data_file=SimpleUploadedFile("doc.txt", b"data"),
            document_type=DocumentType.WAEC,
        )

    return _make


@pytest.fixture
def documentdonor_factory(donor_factory) -> DocumentDonorFactory:
    """Return a callable to build documents for donors."""

    def _make(donor_uname: str) -> DocumentDonor:
        donor = donor_factory(donor_uname)
        return DocumentDonor.objects.create(
            person=donor,
            data_file=SimpleUploadedFile("doc.txt", b"data"),
            document_type=DocumentType.WAEC,
        )

    return _make


@pytest.fixture
def documentstaff_factory(staff_factory) -> DocumentStaffFactory:
    """Return a callable to build documents for Staff."""

    def _make(staff_uname: str) -> DocumentStaff:
        staff = staff_factory(staff_uname)
        return DocumentStaff.objects.create(
            person=staff,
            data_file=SimpleUploadedFile("doc.txt", b"data"),
            document_type=DocumentType.WAEC,
        )

    return _make
