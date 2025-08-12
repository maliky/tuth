"""Test donor scholarship module."""

from datetime import date

import pytest
from django.contrib.auth import get_user_model

from app.finance.models import Scholarship
from app.people.models.donor import Donor
from app.people.models.student import Student


@pytest.mark.django_db
def test_scholarship_links_donor_student(donor_factory, student_factory):
    """Test the link of in scholarship between donor and students."""
    donor = donor_factory("Generous_donor")
    student = student_factory("Studious TU", "BSc Math")

    scholarship = Scholarship.objects.create(
        donor=donor,
        student=student,
        amount=1000,
        start_date=date.today(),
        conditions="Merit based, it's so good",
    )

    assert scholarship.donor == donor
    assert scholarship.student == student


#>TODO would be good to test the reverse relations.  donor.scholarships and student_scholarships
