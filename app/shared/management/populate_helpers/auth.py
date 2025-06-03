"""Auth module."""

from app.shared.constants.perms import UserRole
from django.contrib.auth.models import Group, User
from django.utils import timezone
from typing import Dict
from django.core.management.base import BaseCommand
from app.academics.models import College

from app.shared.constants import DEFAULT_ROLE_TO_COLLEGE, TEST_PW
from app.people.models import RoleAssignment

from .utils import log


def ensure_superuser(cmd: BaseCommand) -> None:
    su = dict(username="dev", email="dev@tu.koba.sarl", password="dev")
    User.objects.filter(username=su["username"]).delete()
    User.objects.create_superuser(**su)
    log(cmd, msg="✔ Superuser recreated.", style="SUCCESS")


def ensure_role_groups() -> Dict[str, Group]:
    return {
        role: Group.objects.get_or_create(name=role.capitalize())[0]
        for role, label in UserRole
    }


def upsert_test_users_and_roles(
    cmd: BaseCommand, colleges: Dict[str, College], groups: Dict[str, Group]
) -> None:
    for role, _ in UserRole:
        user, _ = User.objects.get_or_create(username=f"test_{role}")
        user.is_staff = True
        user.set_password(TEST_PW)
        user.save()
        user.groups.add(groups[role])

        college = colleges.get(DEFAULT_ROLE_TO_COLLEGE.get(role, ""))
        RoleAssignment.objects.update_or_create(
            user=user,
            role=role,
            college=college,
            defaults={"start_date": timezone.now().date(), "end_date": None},
        )
        log(cmd, f"  ↳ {user.username} ({role})")
