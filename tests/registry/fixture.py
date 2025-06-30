"""Test fixtures for the registry app."""

from __future__ import annotations

from decimal import Decimal
from typing import Callable, TypeAlias

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile

from app.registry.choices import DocumentType, StatusRegistration
from app.registry.models import ClassRoster, Document, Grade, Registration

RegistrationFactory: TypeAlias = Callable[[str, str, str, str], Registration]
GradeFactory: TypeAlias = Callable[[str, str, str, str, Decimal], Grade]
DocumentFactory: TypeAlias = Callable[[str, str], Document]
ClassRosterFactory: TypeAlias = Callable[[str, str], ClassRoster]

DECIMAL_90 = Decimal("90")


@pytest.fixture
def registration(student, section) -> Registration:
    """Default registration for a student."""

    return Registration.objects.create(student=student, section=section)


@pytest.fixture
def grade(student, section) -> Grade:
    """Default grade for a student in a section."""

    return Grade.objects.create(
        student=student,
        section=section,
        letter_grade="A",
        numeric_grade=Decimal("90"),
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


@pytest.fixture
def class_roster(section) -> ClassRoster:
    """Default class roster for a section."""

    return ClassRoster.objects.create(section=section)


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

        return Grade.objects.create(
            student=student_factory(student_uname, curri_short_name),
            section=section_factory(course_number, curri_short_name),
            letter_grade=letter,
            numeric_grade=numeric,
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


@pytest.fixture
def class_roster_factory(section_factory) -> ClassRosterFactory:
    """Return a callable to build class rosters."""

    def _make(course_number: str, curri_short_name: str) -> ClassRoster:
        return ClassRoster.objects.create(
            section=section_factory(course_number, curri_short_name)
        )

    return _make
