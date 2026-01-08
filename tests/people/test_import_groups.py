"""Tests for importing users and assigning groups to them."""

from app.people.models.student import Student
import pytest
from tablib import Dataset
from django.contrib.auth import get_user_model
from app.people.admin.resources import StudentResource, FacultyResource
from app.people.models.faculty import Faculty
from app.shared.auth.perms import UserRole
from app.people.utils import mk_username, split_name

User = get_user_model()


@pytest.mark.django_db
def test_student_import_assigns_student_group(curriculum, group_factory):
    ds = Dataset()
    ds.headers = ["student_id", "student_name", "curriculum"]

    name = split_name("Alice Example")
    username = Student.mk_username(*name.parts())

    ds.append(["ST1", name.to_string(full=True), curriculum.pk])

    group_factory(UserRole.STUDENT.value.label)

    res = StudentResource().import_data(ds, dry_run=False)

    assert not res.has_errors(), res.row_errors()
    student = Student.objects.get(student_id="ST1")
    user = student.user

    assert user.groups.filter(name=UserRole.STUDENT.value.label).exists()
    assert user.username == username


@pytest.mark.parametrize(
    "long_name,prefix,first,middle,last,suffix,username",
    [
        # ("Gandyu A S", "", "A.", "S.", "Gandyu", "", "asgandyu"),
        # ("A. Molubah", "", "A.", "", "Molubah", "", "amolubah"),
        # ("Gabriel Bedell", "", "Gabriel", "", "Bedell", "", "gabrielbedell"),
        # ("Gab Bedell", "", "Gab", "", "Bedell", "", "gbedell"),
        ("Dylan, John A", "", "John", "A.", "Dylan", "", ""),
    ],
)
@pytest.mark.django_db
def test_faculty_import_assigns_faculty_group(
    long_name, prefix, first, middle, last, suffix, username
):
    # FacultyResource expects instructor-style columns; align the fixture accordingly.
    ds = Dataset()
    ds.headers = [
        "long_name",
        "prefix_name",
        "first_name",
        "middle_name",
        "last_name",
        "suffix_name",
        "username",
    ]
    ds.append([long_name, prefix, first, middle, last, suffix, username])

    res = FacultyResource().import_data(ds, dry_run=False, raise_errors=True)
    assert not res.has_errors()

    faculty = Faculty.objects.first()
    assert faculty is not None, f"{ds.dict}"
    user = faculty.staff_profile.user

    assert user.groups.filter(name=UserRole.FACULTY.value.label).exists()

    if not username:
        username = Faculty.mk_username(first, last, middle=middle, unique=False)

    assert user.username == username, f"{user.username} and {username}"
