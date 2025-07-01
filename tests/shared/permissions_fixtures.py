import datetime
from typing import Callable

import pytest
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from guardian.shortcuts import assign_perm

from app.academics.models.college import College
from app.people.choices import UserRole
from app.people.models.role_assignment import RoleAssignment


def _group_name(role: UserRole) -> str:
    """Return the default group name for a role."""

    return " ".join(part.capitalize() for part in role.value.split("_"))


@pytest.fixture
def role_user_factory(college) -> Callable[[UserRole], User]:
    """Return a callable creating a user, group, and role assignment."""

    def _make(role: UserRole) -> User:
        user = User.objects.create_user(username=f"{role.value}_user")
        group, _ = Group.objects.get_or_create(name=_group_name(role))
        ct = ContentType.objects.get_for_model(College)
        perm = Permission.objects.get(codename="view_college", content_type=ct)
        group.permissions.add(perm)
        user.groups.add(group)
        RoleAssignment.objects.create(
            user=user,
            role=role,
            college=college,
            start_date=datetime.date.today(),
        )
        assign_perm("view_college", user, college)
        return user

    return _make


@pytest.fixture
def dean_user(role_user_factory) -> User:
    return role_user_factory(UserRole.DEAN)


@pytest.fixture
def chair_user(role_user_factory) -> User:
    return role_user_factory(UserRole.CHAIR)


@pytest.fixture
def faculty_user(role_user_factory) -> User:
    return role_user_factory(UserRole.FACULTY)


@pytest.fixture
def student_user(role_user_factory) -> User:
    return role_user_factory(UserRole.STUDENT)


@pytest.fixture
def college_other(college_factory):
    """Secondary college for permission checks."""

    return college_factory(code="COBA")
