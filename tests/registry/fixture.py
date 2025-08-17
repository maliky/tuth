"""Test fixtures for the registry app."""

from __future__ import annotations

from decimal import Decimal
from typing import Callable, Generator, TypeAlias

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from app.registry.models.document import DocumentType
from app.registry.models import (
    DocumentStudent,
    DocumentStaff,
    DocumentDonor,
    Grade,
    Registration,
)
from app.registry.models.grade import GradeValue

RegistrationFactory: TypeAlias = Callable[[str, str, str, int], Registration]
GradeFactory: TypeAlias = Callable[[str, str, str, str, Decimal], Grade]
DocumentStudentFactory: TypeAlias = Callable[[str, str], DocumentStudent]
DocumentStaffFactory: TypeAlias = Callable[[str], DocumentStaff]
DocumentDonorFactory: TypeAlias = Callable[[str], DocumentDonor]
DocumentTypeFactory: TypeAlias = Callable[[str], Generator[DocumentType, None, None]]

DECIMAL_90 = Decimal("90")


@pytest.fixture
def data_file():
    """Provide a simple data file."""
    return SimpleUploadedFile("doc.txt", b"data")


@pytest.fixture
def registration(student, section) -> Generator[Registration]:
    """Default registration for a student."""
    reg = Registration.objects.create(student=student, section=section)
    yield reg
    # try
    reg.delete()


@pytest.fixture
def grade(student, section, grade_value) -> Grade:
    """Default grade for a student in a section."""
    return Grade.objects.create(
        student=student,
        section=section,
        value=grade_value,
    )


@pytest.fixture
def documentType() -> Generator[DocumentType]:
    """Return a default documentType."""
    _doc_type = DocumentType.get_default()
    yield _doc_type
    _doc_type.delete()


@pytest.fixture
def documentStudent(
    student, data_file, documenttype_factory
) -> Generator[DocumentStudent]:
    """Default document attached to a student."""
    waec = documenttype_factory("waec")

    _doc_stud = DocumentStudent.objects.create(
        person=student, data_file=data_file, document_type=waec
    )
    yield _doc_stud
    _doc_stud.delete()


@pytest.fixture
def documentDonor(donor, data_file, documenttype_factory) -> Generator[DocumentDonor]:
    """Default document attached to a student."""
    acc_letter = documenttype_factory("letter_of_accredidation")
    _doc_donor = DocumentDonor.objects.create(
        person=donor, data_file=data_file, document_type=acc_letter
    )
    yield _doc_donor
    _doc_donor.delete()


@pytest.fixture
def documentStaff(staff, data_file, documenttype_factory) -> Generator[DocumentStaff]:
    """Default document attached to a student."""
    ref_letter = documenttype_factory("letter_of_reference")
    _doc_staff = DocumentStaff.objects.create(
        person=staff, data_file=data_file, document_type=ref_letter
    )
    yield _doc_staff
    _doc_staff.delete()


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
        semester_number: int = 1,
    ) -> Registration:
        _stud = student_factory(student_uname, curri_short_name)
        _sect = section_factory(course_number, curri_short_name, 1, semester_number)
        return Registration.objects.create(student=_stud, section=_sect)

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
def documenttype_factory() -> DocumentTypeFactory:
    """Return a callable to build document type."""

    def _make(code="other") -> Generator[DocumentType]:
        _doc_type = DocumentType.objects.create(code=code)
        yield _doc_type
        _doc_type.delete()

    return _make


@pytest.fixture
def documentstudent_factory(
    student_factory, documenttype_factory, data_file
) -> DocumentStudentFactory:
    """Return a callable to build documents for Students."""

    def _make(student_uname: str, curri_short_name: str) -> DocumentStudent:
        student = student_factory(student_uname, curri_short_name)
        waec = documenttype_factory("waec")

        return DocumentStudent.objects.create(
            person=student,
            data_file=data_file,
            document_type=waec,
        )

    return _make


@pytest.fixture
def documentdonor_factory(
    donor_factory, documenttype_factory, data_file
) -> DocumentDonorFactory:
    """Return a callable to build documents for donors."""

    def _make(donor_uname: str) -> DocumentDonor:
        donor = donor_factory(donor_uname)
        acc_letter = documenttype_factory("letter_of_accreditation")

        return DocumentDonor.objects.create(
            person=donor, data_file=data_file, document_type=acc_letter
        )

    return _make


@pytest.fixture
def documentstaff_factory(
    staff_factory, documenttype_factory, data_file
) -> DocumentStaffFactory:
    """Return a callable to build documents for Staff."""

    def _make(staff_uname: str) -> DocumentStaff:
        staff = staff_factory(staff_uname)
        ref_letter = documenttype_factory("letter_of_reference")

        return DocumentStaff.objects.create(
            person=staff, data_file=data_file, document_type=ref_letter
        )

    return _make
