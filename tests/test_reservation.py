import pytest
from django.core.exceptions import ValidationError
from app.people.models import StudentProfile
from app.timetable.models import Section, Semester, AcademicYear, Reservation
from app.academics.models import Course, College


@pytest.mark.django_db
def test_student_reservation_credit_limit():
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


@pytest.mark.django_db
def test_reservation_mark_paid_creates_payment():
    college = College.objects.create(code="COAS", fullname="College of Arts and Sciences")
    course = Course.objects.create(
        name="TEST2", number="102", title="Test Course 2", credit_hours=3, college=college
    )
    year = AcademicYear.objects.create(start_date="2027-09-01", end_date="2028-08-31")
    semester = Semester.objects.create(
        academic_year=year, number=1, start_date="2027-09-01", end_date="2028-01-15"
    )
    student = StudentProfile.objects.create(student_id="S999999")
    section = Section.objects.create(
        course=course, semester=semester, number=1, max_seats=30
    )

    reservation = Reservation.objects.create(student=student, section=section)
    reservation.full_clean()
    reservation.save()

    User = get_user_model()
    user = User.objects.create(username="cashier")
    reservation.mark_paid(user)

    assert reservation.status == "paid"
    assert reservation.payment.amount == reservation.fee_total
