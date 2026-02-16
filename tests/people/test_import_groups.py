"""Tests for importing users and assigning groups to them."""

from app.people.models.donor import Donor
from app.people.models.staffs import Staff
from app.people.models.student import Student
import pytest
from tablib import Dataset
from django.contrib.auth import get_user_model
from app.people.admin.resources import (
    DonorResource,
    StaffResource,
    StdResource,
    FacultyResource,
)
from app.people.models.faculty import Faculty
from app.shared.auth.perms import UserRole
from app.people.utils import mk_username, name_parts_from_row, parse_name, split_name

User = get_user_model()


@pytest.mark.parametrize(
    "student_id,long_name,username",
    [
        ("ST10007", "Alice Example", ""),
    ],
)
@pytest.mark.django_db
def test_std_import(student_id, long_name, username, curriculum, gp_factory):
    ds = Dataset()

    # username is mandatory for a student
    ds.headers = ["student_id", "long_name", "username", "curriculum"]

    raw_row = [student_id, long_name, "", curriculum.short_name]
    ds.append(raw_row)
    row = dict(zip(ds.headers, raw_row))

    # Create the username before the Resource call otherways it will differ if
    # because by default uniqueness is set to True
    _n = name_parts_from_row(row, fullname_key="long_name", fallback_last="Student")
    username = Student.mk_username(*_n.parts())

    res = StdResource().import_data(ds, dry_run=False)
    assert not res.has_errors(), res.row_errors()

    student = Student.objects.get(student_id="ST10007")
    assert student.user.groups.filter(name=UserRole.STUDENT.value.label).exists()

    # check that the generation of username is correct through the import
    assert student.user.username == username, f"{student.user.username, username}"


@pytest.mark.parametrize(
    "long_name,prefix,first,middle,last,suffix,username",
    [
        ("Gandyu A S", "", "A.", "S.", "Gandyu", "", "asgandyu"),
        ("A. Molubah", "", "A.", "", "Molubah", "", "a.molubah"),
        ("Gabriel Bedell", "", "Gabriel", "", "Bedell", "", "gbedell"),
        ("Gab Bedell", "", "Gab", "", "Bedell", "", "gab.bedell"),
        ("Dylan, John A", "", "John", "A.", "Dylan", "", ""),
    ],
)
@pytest.mark.django_db
def test_faculty_import(long_name, prefix, first, middle, last, suffix, username):
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

    if not username:
        username = Faculty.mk_username(first, last, middle=middle)

    res = FacultyResource().import_data(ds, dry_run=False, raise_errors=True)
    assert not res.has_errors()

    faculty = Faculty.objects.first()
    assert faculty is not None, f"{ds.dict}"

    user = faculty.staff_profile.user
    assert user.groups.filter(name=UserRole.FACULTY.value.label).exists()
    assert user.username == username, f"{user.username, username}"


@pytest.mark.parametrize(
    "long_name,prefix,first,middle,last,suffix,username",
    [
        ("Chinois A S", "", "A.", "S.", "Chinois", "", "as.chinois"),
        ("Dylan, Gad Alfonse", "", "Gad", "A.", "Dylan", "", ""),
    ],
)
@pytest.mark.django_db
def test_staff_import(long_name, prefix, first, middle, last, suffix, username):
    # StaffResource expects instructor-style columns; align the fixture accordingly.
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

    if not username:
        username = Staff.mk_username(first, last, middle=middle)

    # import ipdb; ipdb.set_trace()

    res = StaffResource().import_data(ds, dry_run=False, raise_errors=True)
    assert not res.has_errors()

    staff = Staff.objects.first()
    assert staff is not None, f"{ds.dict}"

    user = staff.user
    assert user.groups.filter(name=UserRole.STAFF.value.label).exists()

    assert user.username == username, f"{user.username, username}"


@pytest.mark.parametrize(
    "donors,username", [("Apple Newton", ""), ("Bob Dylan", "bdylan")]
)
@pytest.mark.django_db
def test_donor_import(donors, username):
    # FacultyResource expects instructor-style columns; align the fixture accordingly.
    ds = Dataset()
    ds.headers = ["donors", "username"]
    ds.append([donors, username])

    if not username:
        name = parse_name(donors)
        username = Donor.mk_username(*name.parts(), unique=False)

    res = DonorResource().import_data(ds, dry_run=False, raise_errors=True)
    assert not res.has_errors()

    donor = Donor.objects.first()
    assert donor is not None, f"{ds.dict}"

    user = donor.user
    assert user.groups.filter(name=UserRole.DONOR.value.label).exists()
    assert user.username == username, f"{user.username, username}"
