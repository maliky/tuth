"""Test for creating faculty from the people app."""

import pytest

from app.people.repositories import PeopleRepository

# from tests.fixtures.academics import college_factory, college


@pytest.mark.django_db
def test_get_or_create_faculty_idempotent(college):
    faculty_one = PeopleRepository.get_or_create_faculty("John Doe", college)
    faculty_two = PeopleRepository.get_or_create_faculty("John Doe", college)
    assert faculty_one.pk == faculty_two.pk, f"{faculty_one} {faculty_two}"
    assert faculty_one.college == college, f"{faculty_one.college} {college}"


@pytest.mark.django_db
def test_get_or_create_faculty_updates_college(college_factory):
    college_a = college_factory(code="COAS")
    college_b = college_factory(code="COBA")

    faculty = PeopleRepository.get_or_create_faculty("Jane Doe", college_a)
    assert faculty.college == college_a

    same_faculty = PeopleRepository.get_or_create_faculty("Jane Doe", college_b)
    faculty.refresh_from_db()

    assert faculty.pk == same_faculty.pk, f"{faculty} {same_faculty}"
    assert faculty.college == college_b, f"{faculty.college} {college_b}"
