"""Tests for importing users and assigning groups to them."""

import pytest
from tablib import Dataset
from django.contrib.auth import get_user_model
from app.people.admin.resources import StudentResource, FacultyResource
from app.people.choices import UserRole
from app.people.utils import mk_username

User = get_user_model()


@pytest.mark.django_db
def test_student_import_assigns_student_group(curriculum):
    ds = Dataset()
    ds.headers = ["student_id", "student_name", "curriculum"]
    ds.append(["ST1", "Alice Example", curriculum.pk])
    res = StudentResource().import_data(ds, dry_run=False)
    assert not res.has_errors(), res.row_errors()
    user = User.objects.get(username="alice.example")
    assert user.groups.filter(name=UserRole.STUDENT.label).exists()


@pytest.mark.django_db
def test_faculty_import_assigns_faculty_group(college):
    ds = Dataset()
    ds.headers = ["faculty"]
    ds.append(["Bob Example"])
    res = FacultyResource().import_data(ds, dry_run=False)
    assert not res.has_errors()
    username = mk_username("Bob", "Example", unique=False)
    user = User.objects.get(username=username)
    assert user.groups.filter(name=UserRole.FACULTY.label).exists()
