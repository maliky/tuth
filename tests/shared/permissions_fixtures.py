"""Test fixtures for the permissions module."""

import datetime
from typing import Callable, TypeAlias

import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from guardian.shortcuts import assign_perm

from app.academics.models.college import College
from app.shared.auth.perms import UserRole
from app.people.models.role_assignment import RoleAssignment

RoleUserFactory: TypeAlias = Callable[[UserRole], User]


def _group_name(role: UserRole) -> str:
    """Return the default group name for a role."""

    # Im' not sure abou the groupe name is it Finance Officer or finance_officer
    return role.value.label


@pytest.fixture
def role_user_factory(college_factory, user_factory, group_factory) -> RoleUserFactory:
    """Return a callable creating a user, group, and role assignment.

    Returns the user in a group, with permission to view a college.
    """

    def _make(ur: UserRole) -> User:
        college = college_factory()
        user: User = user_factory(username=f"{ur.value.code}_tuser")

        group = group_factory(name=_group_name(ur))
        ct = ContentType.objects.get_for_model(College)
        perm = Permission.objects.get(codename="view_college", content_type=ct)

        group.permissions.add(perm)
        user.groups.add(group)

        RoleAssignment.objects.create(
            user=user,
            role=ur.value.code,
            college=college,
            start_date=datetime.date.today(),
        )
        # guardian ->
        assign_perm("view_college", user, college)

        return user

    return _make


@pytest.fixture
def registrar_officer(role_user_factory) -> User:
    """Return a User with role (group) registrar officer."""
    role_officer: User = role_user_factory(UserRole.REGISTRAR_OFFICER)
    return role_officer


@pytest.fixture
def finance_officer(role_user_factory) -> User:
    """Return a User with role (group) finaance officer."""
    finance_officer: User = role_user_factory(UserRole.FINANCE_OFFICER)
    return finance_officer


# @pytest.fixture
# def basic_user(user_factory, curriculum, semester):
#     user = user_factory("plain")
#     Student.objects.create(
#         user=user, curriculum=curriculum, current_enroled_semester=semester
#     )
#     return user


@pytest.fixture
def dean_user(role_user_factory) -> User:
    """Return a Dean."""
    dean_user: User = role_user_factory(UserRole.DEAN)
    return dean_user


@pytest.fixture
def chair_user(role_user_factory) -> User:
    """Return a User with role (group) Chair."""
    chair_user: User = role_user_factory(UserRole.CHAIR)
    return chair_user


@pytest.fixture
def faculty_user(role_user_factory) -> User:
    """Return a User with role (group) faculty?"""
    faculty: User = role_user_factory(UserRole.FACULTY)
    return faculty


@pytest.fixture
def student_user(role_user_factory) -> User:
    """Return a User with role (group) student?"""
    student_user: User = role_user_factory(UserRole.STUDENT)
    return student_user


@pytest.fixture
def college_other(college_factory):
    """Secondary college for permission checks."""

    return college_factory(code="COBA")
