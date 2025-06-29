"""Test fixtures for the registry app."""

from __future__ import annotations

from decimal import Decimal
from typing import Callable, TypeAlias

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile

from app.registry.choices import DocumentType, StatusRegistration
from app.registry.models import ClassRoster, Document, Grade, Registration
from app.people.models.student import Student
from app.timetable.models.section import Section

DocumentFactory: TypeAlias = Callable[[Student], Document]
RegistrationFactory: TypeAlias = Callable[[Student, Section], Registration]
GradeFactory: TypeAlias = Callable[[Student, Section, str], Grade]
ClassRosterFactory: TypeAlias = Callable[[Section], ClassRoster]


@pytest.fixture
def registration(student: Student, section: Section) -> Registration:
    """Default registration for a student."""

    return Registration.objects.create(student=student, section=section)


@pytest.fixture
def grade(student: Student, section: Section) -> Grade:
    """Default grade for a student in a section."""

    return Grade.objects.create(
        student=student,
        section=section,
        letter_grade="A",
        numeric_grade=Decimal("90"),
    )


@pytest.fixture
def document(student: Student) -> Document:
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
def class_roster(section: Section) -> ClassRoster:
    """Default class roster for a section."""

    return ClassRoster.objects.create(section=section)


# ─── factory fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def registration_factory() -> RegistrationFactory:
    """Return a callable to build registrations."""

    def _make(
        student: Student,
        section: Section,
        status: str = StatusRegistration.PENDING,
    ) -> Registration:
        return Registration.objects.create(
            student=student,
            section=section,
            status=status,
        )

    return _make


@pytest.fixture
def grade_factory() -> GradeFactory:
    """Return a callable to build grades."""

    def _make(
        student: Student,
        section: Section,
        letter: str = "A",
        numeric: Decimal = Decimal("90"),
    ) -> Grade:
        return Grade.objects.create(
            student=student,
            section=section,
            letter_grade=letter,
            numeric_grade=numeric,
        )

    return _make


@pytest.fixture
def document_factory() -> DocumentFactory:
    """Return a callable to build documents."""

    def _make(student: Student) -> Document:
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
def class_roster_factory() -> ClassRosterFactory:
    """Return a callable to build class rosters."""

    def _make(section: Section) -> ClassRoster:
        return ClassRoster.objects.create(section=section)

    return _make

