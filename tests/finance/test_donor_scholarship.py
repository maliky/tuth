"""Test donor scholarship module."""

# from datetime import date

# import pytest
# from app.finance.models import Scholarship


# @pytest.mark.django_db
# def test_scholarship_links_donor_student(donor_factory, std_factory):
#     """Test the link of in scholarship between donor and students."""
#     donor = donor_factory("Generous_donor")
#     student = std_factory("Studious TU", "BSc Math")

#     scholarship = Scholarship.objects.create(
#         donor=donor,
#         student=student,
#         amount=1000,
#         start_date=date.today(),
#         conditions="Merit based, it's so good",
#     )

#     assert scholarship.donor == donor
#     assert scholarship.student == student


# TODO: add reverse relation tests for donor.scholarships and student_scholarships.
