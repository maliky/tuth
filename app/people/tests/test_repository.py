"""Test for creating faculty from the people app."""

import pytest

from app.people.repositories import PeopleRepository


@pytest.mark.django_db
def test_get_or_create_faculty_idempotent(college):
    faculty_one = PeopleRepository.get_or_create_faculty("John Doe", college)
    faculty_two = PeopleRepository.get_or_create_faculty("John Doe", college)
    assert faculty_one.pk == faculty_two.pk
    assert faculty_one.college == college


@pytest.mark.django_db
def test_get_or_create_faculty_updates_college(college_factory):
    college_a = college_factory(code="COAS")
    college_b = college_factory(code="COBA")

    faculty = PeopleRepository.get_or_create_faculty("Jane Doe", college_a)
    assert faculty.college == college_a

    same_faculty = PeopleRepository.get_or_create_faculty("Jane Doe", college_b)
    faculty.refresh_from_db()

    assert faculty.pk == same_faculty.pk
    assert faculty.college == college_b
