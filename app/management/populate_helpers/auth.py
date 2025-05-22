from django.contrib.auth.models import Group, User
from django.utils import timezone

from app.shared.constants import DEFAULT_ROLE_TO_COLLEGE, TEST_PW, USER_ROLES
from app.people.models import RoleAssignment

from .utils import log


def ensure_superuser(cmd):
    su = dict(username="dev", email="dev@tu.koba.sarl", password="dev")
    User.objects.filter(username=su["username"]).delete()
    User.objects.create_superuser(**su)
    log(cmd, msg="✔ Superuser recreated.", style="SUCCESS")


def ensure_role_groups():
    return {
        role: Group.objects.get_or_create(name=role.capitalize())[0]
        for role in USER_ROLES
    }


def upsert_test_users_and_roles(cmd, colleges, groups):
    for role in USER_ROLES:
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
