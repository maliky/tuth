import pytest
from datetime import date
from django.contrib.auth import get_user_model

from app.people.models import DonorProfile, StudentProfile
from app.finance.models import Scholarship


@pytest.mark.django_db
def test_donor_profile_creation():
    User = get_user_model()
    user = User.objects.create(username="donor")
    donor = DonorProfile.objects.create(user=user, donor_id="D001")

    assert donor.donor_id == "D001"


@pytest.mark.django_db
def test_scholarship_links_donor_student():
    User = get_user_model()
    d_user = User.objects.create(username="donor")
    s_user = User.objects.create(username="stud")

    donor = DonorProfile.objects.create(user=d_user, donor_id="D002")
    student = StudentProfile.objects.create(
        user=s_user,
        student_id="S001",
        enrollment_semester=1,
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
