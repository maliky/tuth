"""Helpers to create demo users and roles during data population."""

from typing import Dict

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from app.shared.auth.perms import UserRole
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
        user_role.value.code: Group.objects.get_or_create(name=user_role.value.group)[0]
        for user_role in UserRole
    }
