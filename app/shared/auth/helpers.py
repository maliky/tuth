"""Helpers to create demo users and roles during data population."""

from typing import Dict

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.utils import timezone

from app.academics.models.college import College
from app.shared.auth.perms import UserRole
from app.people.models.role_assignment import RoleAssignment
from app.shared.auth.perms import DEFAULT_ROLE_TO_COLLEGE, TEST_PW
from app.shared.csv.utils import log

User = get_user_model()


def ensure_superuser(cmd: BaseCommand) -> None:
    """Recreate the default development superuser."""

    su = dict(username="dev", email="dev@tu.koba.sarl", password="dev")
    User.objects.filter(username=su["username"]).delete()
    User.objects.create_superuser(**su)
    log(cmd, msg="✔ Superuser recreated.", style="SUCCESS")


def ensure_role_groups() -> Dict[str, Group]:
    """Create missing Group objects for each user role."""

    return {
        role: Group.objects.get_or_create(name=role.capitalize())[0]
        for role, label in UserRole
    }


def upsert_test_users_and_roles(
    cmd: BaseCommand, colleges: Dict[str, College], groups: Dict[str, Group]
) -> None:
    """Create test users for each role and associate default colleges."""

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
            defaults={
                "start_date": timezone.now().date(),
                "end_date": None,
                "department": None,
            },
        )
        log(cmd, f"  ↳ {user.username} ({role})")
