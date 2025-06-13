"""Test reservation module."""
import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from app.shared.constants import StatusReservation
from app.timetable.models import Reservation


# ─── credit-hour limit ───────────────────────────────────────────────────────
@pytest.mark.django_db
def test_student_reservation_credit_limit(student_profile, section_factory):
    """
    A seventh 3-credit reservation must trigger the credit-hour validator.
    """
    # six valid reservations → 18 credits
    for i in range(1, 7):
        Reservation.objects.create(
            student=student_profile,
            section=section_factory(i),
            status=StatusReservation.REQUESTED,
        )

    # seventh reservation → exceeds 18 credits
    extra_res = Reservation(
        student=student_profile,
        section=section_factory(7),
        status=StatusReservation.REQUESTED,
    )

    with pytest.raises(ValidationError, match="Exceeded credit-hour limit"):
        extra_res.full_clean()


# ─── mark_paid workflow ──────────────────────────────────────────────────────
@pytest.mark.django_db
def test_reservation_mark_paid_creates_payment(
    student_profile, staff_profile, section_factory
):
    res = Reservation.objects.create(
        student=student_profile,
        section=section_factory(1),
    )
    res.validate()  # status -> validated
    res.mark_paid(staff_profile)  # status -> paid + Payment row

    assert res.status == StatusReservation.PAID
    assert res.payment.amount == res.fee_total
    assert res.status_history.first().status == StatusReservation.PAID


# ─── cancellation ────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_cancel_reservation_decrements_section_count(student_profile, section_factory):
    sec = section_factory(1)
    res = Reservation.objects.create(student=student_profile, section=sec)
    res.validate()
    sec.refresh_from_db()
    assert sec.current_registrations == 1

    res.cancel()
    sec.refresh_from_db()
    assert res.status == StatusReservation.CANCELLED
    assert sec.current_registrations == 0


# ─── deletion ────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_delete_reservation_decrements_section_count(student_profile, section_factory):
    sec = section_factory(1)
    res = Reservation.objects.create(student=student_profile, section=sec)
    res.validate()
    sec.refresh_from_db()
    assert sec.current_registrations == 1

    res.delete()
    sec.refresh_from_db()
    assert sec.current_registrations == 0


# ─── dashboard view ──────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_student_dashboard_url(client, superuser):
    """
    Basic smoke test – dashboard should load for an authenticated student.
    """
    from app.people.models import Student

    Student.objects.create(
        user=superuser,
        student_id="SUPER",
        enrollment_semester=1,
    )
    client.force_login(superuser)

    resp = client.get(reverse("student_dashboard"))
    assert resp.status_code == 200
