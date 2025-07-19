"""Test fixtures for the registry app."""

from __future__ import annotations

from decimal import Decimal
from typing import Callable, TypeAlias

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile

from app.registry.choices import DocumentType, StatusRegistration
from app.registry.models import Document, Grade, Registration
from app.registry.models.grade import GradeType

RegistrationFactory: TypeAlias = Callable[[str, str, str, str], Registration]
GradeFactory: TypeAlias = Callable[[str, str, str, str, Decimal], Grade]
DocumentFactory: TypeAlias = Callable[[str, str], Document]

DECIMAL_90 = Decimal("90")


@pytest.fixture
def registration(student, section) -> Registration:
    """Default registration for a student."""

    return Registration.objects.create(student=student, section=section)


@pytest.fixture
def grade(student, section) -> Grade:
    """Default grade for a student in a section."""

    grade_type = GradeType.objects.create(code="A")
    return Grade.objects.create(
        student=student,
        section=section,
        grade=grade_type,
    )


@pytest.fixture
def document(student) -> Document:
    """Default document attached to a student."""

    ct = ContentType.objects.get_for_model(student)
    file_data = SimpleUploadedFile("doc.txt", b"data")
    return Document.objects.create(
        profile_type=ct,
        profile_id=student.id,
        data_file=file_data,
        document_type=DocumentType.WAEC,
    )




# ─── factory fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def registration_factory(student_factory, section_factory) -> RegistrationFactory:
    """Return a callable to build registrations."""

    #    TODO
    def _make(
        student_uname: str,
        curri_short_name: str,
        course_number: str,
        status: str = StatusRegistration.PENDING,
    ) -> Registration:
        return Registration.objects.create(
            student=student_factory(student_uname, curri_short_name),
            section=section_factory(course_number, curri_short_name),
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

        grade_type, _ = GradeType.objects.get_or_create(code=letter)
        return Grade.objects.create(
            student=student_factory(student_uname, curri_short_name),
            section=section_factory(course_number, curri_short_name),
            grade=grade_type,
        )

    return _make


@pytest.fixture
def document_factory(student_factory) -> DocumentFactory:
    """Return a callable to build documents."""

    def _make(student_uname: str, curri_short_name: str) -> Document:
        student = student_factory(student_uname, curri_short_name)
        ct = ContentType.objects.get_for_model(student)
        file_data = SimpleUploadedFile("doc.txt", b"data")
        return Document.objects.create(
            profile_type=ct,
            profile_id=student.id,
            data_file=file_data,
            document_type=DocumentType.WAEC,
        )

    return _make


