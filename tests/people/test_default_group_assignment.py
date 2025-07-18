import pytest
from app.people.choices import UserRole


@pytest.mark.django_db
def test_student_creation_gets_student_group(student):
    user = student.user
    assert user.groups.filter(name=UserRole.STUDENT.label).exists()
    assert not user.is_staff


@pytest.mark.django_db
def test_faculty_creation_gets_faculty_group_and_staff(faculty):
    user = faculty.staff_profile.user
    assert user.groups.filter(name=UserRole.FACULTY.label).exists()
    assert user.is_staff


@pytest.mark.django_db
def test_donor_creation_gets_donor_group_and_not_staff(donor):
    user = donor.user
    assert user.groups.filter(name=UserRole.DONOR.label).exists()
    assert not user.is_staff
