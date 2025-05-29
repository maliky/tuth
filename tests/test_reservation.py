import pytest
from django.core.exceptions import ValidationError
from app.people.models import StudentProfile
from app.timetable.models import Section, Semester, AcademicYear, Reservation
from app.academics.models import Course, College


@pytest.mark.django_db
def test_student_reservation_credit_limit():
    # Create academic context
    college = College.objects.create(code="COAS", fullname="College of Arts and Sciences")
    course = Course.objects.create(
        name="TEST", number="101", title="Test Course", credit_hours=3, college=college
    )
    year = AcademicYear.objects.create(start_date="2025-09-01", end_date="2026-08-31")
    semester = Semester.objects.create(
        academic_year=year, number=1, start_date="2025-09-01", end_date="2026-01-15"
    )

    # Create student profile
    student = StudentProfile.objects.create(student_id="S123456")

    # Create 7 sections of 3 credits each (21 credits total)
    sections = [
        Section.objects.create(
            course=course, semester=semester, number=i + 1, max_seats=30
        )
        for i in range(7)
    ]

    # Reserve first 6 sections without issues (18 credits)
    for sec in sections[:6]:
        Reservation.objects.create(student=student, section=sec, status="requested")

    # Attempt to reserve the 7th section (3 more credits should fail)
    reservation = Reservation(student=student, section=sections[6], status="requested")

    with pytest.raises(ValidationError) as exc_info:
        reservation.full_clean()  # Trigger the validation explicitly

    assert "Exceeded credit-hour limit" in str(exc_info.value)


@pytest.mark.django_db
def test_student_reservation_credit_limit_backlog():
    """Creating a seventh 3-credit reservation should raise a validation error."""

    # Set up course and semester
    college = College.objects.create(code="COAS", fullname="College of Arts and Sciences")
    course = Course.objects.create(
        name="TEST", number="102", title="Backlog Course", credit_hours=3, college=college
    )
    year = AcademicYear.objects.create(start_date="2025-09-01", end_date="2026-08-31")
    semester = Semester.objects.create(
        academic_year=year, number=1, start_date="2025-09-01", end_date="2026-01-15"
    )

    # Student already holds six reservations worth three credits each
    student = StudentProfile.objects.create(student_id="S654321")
    sections = [
        Section.objects.create(
            course=course, semester=semester, number=i + 1, max_seats=30
        )
        for i in range(6)
    ]
    for sec in sections:
        Reservation.objects.create(student=student, section=sec, status="requested")

    # Attempt to create a seventh reservation of three credits
    extra_section = Section.objects.create(
        course=course, semester=semester, number=7, max_seats=30
    )
    reservation = Reservation(student=student, section=extra_section, status="requested")

    with pytest.raises(ValidationError) as exc_info:
        reservation.full_clean()

    assert "Exceeded credit-hour limit" in str(exc_info.value)
