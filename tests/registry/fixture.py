"""Test fixtures for the registry app."""

from __future__ import annotations

from decimal import Decimal
from typing import Callable, Generator, TypeAlias

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from app.registry.models.document import DocType
from app.registry.models import (
    DocStd,
    DocStaff,
    DocDonor,
    Grade,
    Registration,
)
from app.registry.models.grade import GradeValue
from tests.constants import D90

RegistrationFactoryT: TypeAlias = Callable[[str, str, str, int], Registration]
GradeFactoryT: TypeAlias = Callable[[str, str, str, str, Decimal], Grade]
DocStdFactoryT: TypeAlias = Callable[[str, str], DocStd]
DocStaffFactoryT: TypeAlias = Callable[[str], DocStaff]
DocDonorFactoryT: TypeAlias = Callable[[str], DocDonor]
DocTypeFactoryT: TypeAlias = Callable[[str], Generator[DocType, None, None]]


@pytest.fixture
def data_file():
    """Provide a simple data file."""
    return SimpleUploadedFile("doc.txt", b"data")


@pytest.fixture
def registration(student, section) -> Generator[Registration, None, None]:
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
def documentType() -> Generator[DocType, None, None]:
    """Return a default documentType."""
    _doc_type = DocType.get_dft()
    yield _doc_type
    _doc_type.delete()


@pytest.fixture
def documentStd(
    student, data_file, documenttype_factory
) -> Generator[DocStd, None, None]:
    """Default document attached to a student."""
    waec = documenttype_factory("waec")

    _doc_stud = DocStd.objects.create(
        person=student, data_file=data_file, document_type=waec
    )
    yield _doc_stud
    _doc_stud.delete()


@pytest.fixture
def documentDonor(
    donor, data_file, documenttype_factory
) -> Generator[DocDonor, None, None]:
    """Default document attached to a student."""
    acc_letter = documenttype_factory("letter_of_accredidation")
    _doc_donor = DocDonor.objects.create(
        person=donor, data_file=data_file, document_type=acc_letter
    )
    yield _doc_donor
    _doc_donor.delete()


@pytest.fixture
def documentStaff(
    staff, data_file, documenttype_factory
) -> Generator[DocStaff, None, None]:
    """Default document attached to a student."""
    ref_letter = documenttype_factory("letter_of_reference")
    _doc_staff = DocStaff.objects.create(
        person=staff, data_file=data_file, document_type=ref_letter
    )
    yield _doc_staff
    _doc_staff.delete()


# ─── factory fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def regio_factory(std_factory, sec_factory) -> RegistrationFactoryT:
    """Return a callable to build registrations.

    Parameters allow customizing the semester of the created section.
    """

    def _make(
        student_uname: str,
        curri_short_name: str,
        course_number: str,
        semester_number: int = 1,
    ) -> Registration:
        _stud = std_factory(student_uname, curri_short_name)
        _sect = sec_factory(course_number, curri_short_name, 1, semester_number)
        return Registration.objects.create(student=_stud, section=_sect)

    return _make


@pytest.fixture
def grade_factory(std_factory, sec_factory) -> GradeFactoryT:
    """Return a callable to build grades."""

    def _make(
        student_uname: str,
        curri_short_name: str,
        course_number: str,
        letter: str = "A",
        numeric: Decimal = D90,
    ) -> Grade:
        grade_value, _ = GradeValue.objects.get_or_create(code=letter)
        return Grade.objects.create(
            student=std_factory(student_uname, curri_short_name),
            section=sec_factory(course_number, curri_short_name),
            value=grade_value,
        )

    return _make


@pytest.fixture
def documenttype_factory() -> DocTypeFactoryT:
    """Return a callable to build document type."""

    def _make(code="other") -> Generator[DocType, None, None]:
        _doc_type = DocType.objects.create(code=code)
        yield _doc_type
        _doc_type.delete()

    return _make


@pytest.fixture
def documentstd_factory(std_factory, documenttype_factory, data_file) -> DocStdFactoryT:
    """Return a callable to build documents for Stds."""

    def _make(student_uname: str, curri_short_name: str) -> DocStd:
        student = std_factory(student_uname, curri_short_name)
        waec = documenttype_factory("waec")

        return DocStd.objects.create(
            person=student,
            data_file=data_file,
            document_type=waec,
        )

    return _make


@pytest.fixture
def documentdonor_factory(
    donor_factory, documenttype_factory, data_file
) -> DocDonorFactoryT:
    """Return a callable to build documents for donors."""

    def _make(donor_uname: str) -> DocDonor:
        donor = donor_factory(donor_uname)
        acc_letter = documenttype_factory("letter_of_accreditation")

        return DocDonor.objects.create(
            person=donor, data_file=data_file, document_type=acc_letter
        )

    return _make


@pytest.fixture
def documentstaff_factory(
    staff_factory, documenttype_factory, data_file
) -> DocStaffFactoryT:
    """Return a callable to build documents for Staff."""

    def _make(staff_uname: str) -> DocStaff:
        staff = staff_factory(staff_uname)
        ref_letter = documenttype_factory("letter_of_reference")

        return DocStaff.objects.create(
            person=staff, data_file=data_file, document_type=ref_letter
        )

    return _make
