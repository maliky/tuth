"""Test donor scholarship module."""

from datetime import date

import pytest
from django.contrib.auth import get_user_model

from app.finance.models import Scholarship
from app.people.models.donor import Donor
from app.people.models.student import Student


@pytest.mark.django_db
def test_donor_profile_creation():
    User = get_user_model()
    user = User.objects.create(username="donor")
    donor = Donor.objects.create(user=user)

    assert donor.donor_id == f"TU_DNR000{user.id}"


@pytest.mark.django_db
def test_scholarship_links_donor_student(semester):
    User = get_user_model()
    d_user = User.objects.create(username="donor")
    s_user = User.objects.create(username="stud")

    donor = Donor.objects.create(user=d_user)
    student = Student.objects.create(
        user=s_user,
        enrollment_semester=semester,
    )

    scholarship = Scholarship.objects.create(
        donor=donor,
        student=student,
        amount=1000,
        start_date=date.today(),
        conditions="Merit based",
    )

    assert scholarship.donor == donor
    assert scholarship.student == student
