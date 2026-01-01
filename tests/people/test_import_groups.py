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

    name = "Alice Example"
    name_part = split_name(name)

    username = Student.mk_username(name_part.first, name_part.last, name_part.middle)

    ds.append(["ST1", name, curriculum.pk])

    group_factory(UserRole.STUDENT.value.label)

    res = StudentResource().import_data(ds, dry_run=False)

    assert not res.has_errors(), res.row_errors()
    student = Student.objects.get(student_id="ST1")
    user = student.user

    assert user.groups.filter(name=UserRole.STUDENT.value.label).exists()
    assert user.username == username


@pytest.mark.django_db
@pytest.mark.parametrize(
    "staff_profile,name_prefix,first_n,middle_n,last_n,name_suffix,username",
    [
        ("Gandyu A S", "", "A.", "S.", "Gandyu", "", "agandyu"),
        ("A. Molubah", "", "A.", "", "Molubah", "", "amolubah"),
        ("Bedell Gabriel", "", "Gabriel", "", "Bedell", "", "gbedell"),
        ("Gandyu, Alexander S", "", "Alexander", "S.", "Gandyu", "", "agandyu2"),
        ("Dylan, John A", "", "John", "A.", "Dylan", "", ""),
    ],
)
def test_faculty_import_assigns_faculty_group(
    staff_profile, name_prefix, first_n, middle_n, last_n, name_suffix, username
):
    # FacultyResource expects instructor-style columns; align the fixture accordingly.
    ds = Dataset()
    ds.headers = [
        "staff_profile",
        "name_prefix",
        "first_n",
        "middle_n",
        "last_n",
        "name_suffix",
        "username",
    ]
    ds.append(
        [staff_profile, name_prefix, first_n, middle_n, last_n, name_suffix, username]
    )

    res = FacultyResource().import_data(ds, dry_run=False, raise_errors=True)
    assert not res.has_errors()

    faculty = Faculty.objects.first()
    assert faculty is not None
    user = faculty.staff_profile.user

    assert user.groups.filter(name=UserRole.FACULTY.value.label).exists()
    if not username:
        username = Faculty.mk_username(first_n, last_n, middle=middle_n)
    assert user.username == username, f"{user.username} and {username}"
