"""Tests for importing users and assigning groups to them."""

from app.people.models.student import Student
import pytest
from tablib import Dataset
from django.contrib.auth import get_user_model
from app.people.admin.resources import StudentResource, FacultyResource
from app.shared.auth.perms import UserRole
from app.people.utils import mk_username, split_name

User = get_user_model()


@pytest.mark.django_db
def test_student_import_assigns_student_group(curriculum, group_factory):
    ds = Dataset()
    ds.headers = ["student_id", "student_name", "curriculum"]

    name = "Alice Example"
    _, first, middle, last, _ = split_name(name)

    username = Student.mk_username(first, last, middle)

    ds.append(["ST1", name, curriculum.pk])

    group_factory(UserRole.STUDENT.value.label)

    res = StudentResource().import_data(ds, dry_run=False)

    assert not res.has_errors(), res.row_errors()
    user = User.objects.get(username=username)

    assert user.groups.filter(name=UserRole.STUDENT.value.label).exists()


@pytest.mark.django_db
def test_faculty_import_assigns_faculty_group(college):
    ds = Dataset()
    ds.headers = ["faculty"]
    name = "Bob Teaches"
    _, first, middle, last, _ = split_name(name)
    username = mk_username(first, last, middle, prefix_len=2)

    ds.append([name])
    res = FacultyResource().import_data(ds, dry_run=False, raise_errors=True)
    assert not res.has_errors()

    user = User.objects.get(username=username)
    assert user.groups.filter(name=UserRole.FACULTY.value.label).exists()
