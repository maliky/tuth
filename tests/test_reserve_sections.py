"""Test reserve_sections service."""

import pytest
from django.core.exceptions import ValidationError

from app.shared.constants import MAX_STUDENT_CREDITS, StatusReservation
from app.timetable.models import Reservation, Section
from app.timetable.services import reserve_sections


@pytest.fixture
def section_factory(course, semester):
    """Return a factory for Section objects without schedule FK."""

    def _make(number: int) -> Section:
        return Section.objects.create(
            course=course,
            semester=semester,
            number=number,
            faculty=None,
            start_date=semester.start_date,
            end_date=semester.end_date,
            max_seats=30,
        )

    return _make


@pytest.mark.django_db
def test_reserve_sections_creates_reservations_and_increments_seats(
    student_profile, section_factory
):
    """Multiple reservations should be created in one atomic block."""
    sections = [section_factory(1), section_factory(2)]

    reservations = reserve_sections(student_profile, sections)

    assert len(reservations) == 2
    for res, sec in zip(reservations, sections):
        assert res.student == student_profile
        assert res.section == sec
        assert res.status == StatusReservation.REQUESTED
        sec.refresh_from_db()
        assert sec.current_registrations == 1


@pytest.mark.django_db
def test_reserve_sections_enforces_credit_limit(student_profile, section_factory):
    """Exceeding MAX_STUDENT_CREDITS should roll back all changes."""
    sections = [section_factory(i) for i in range(1, 8)]

    with pytest.raises(ValidationError) as exc:
        reserve_sections(student_profile, sections)

    assert str(MAX_STUDENT_CREDITS) in str(exc.value)

    assert Reservation.objects.count() == 0
    for sec in sections:
        sec.refresh_from_db()
        assert sec.current_registrations == 0
