# app/management/commands/populate_initial_data.py
from __future__ import annotations

from datetime import date

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from guardian.shortcuts import assign_perm

# from app.models.timed import AcademicYear, Term, Section

from app.constants import (
    COLLEGE_CHOICES,
    DEFAULT_ROLE_TO_COLLEGE,
    OBJECT_PERM_MATRIX,
    TEST_PW,
    USER_ROLES,
)
from app.models import AcademicYear, College, RoleAssignment


# ────────────────────────────────────────────────────────────────────
# Pure helpers
# ────────────────────────────────────────────────────────────────────


def ensure_superuser():
    SUPERUSER = {"username": "dev", "email": "dev@tu.koba.sarl", "password": "dev"}

    if not User.objects.filter(username=SUPERUSER["username"]).exists():
        User.objects.create_superuser(**SUPERUSER)
        print("✔ Superuser recreated.")
    else:
        print("Superuser already present.")


def populate_academic_years(start_year: int = 2009, end_year: int | None = None) -> None:
    """Insert `AcademicYear` rows from start_year … end_year (inclusive)."""
    if end_year is None:
        end_year = date.today().year

    for year in range(start_year, end_year + 1):
        starting = date(year, 9, 1)  # 1 Sep sits in allowed (Jul-Oct) window
        _, created = AcademicYear.objects.get_or_create(starting_date=starting)
        verb = "Created" if created else "Exists "
        print(f"{verb}: {starting.strftime('%Y')}/{end_year}")


def populate_colleges() -> dict[str, College]:
    """Return mapping code → College instance (created or fetched)."""
    mapping: dict[str, College] = {}
    for code, fullname in COLLEGE_CHOICES:
        obj, _ = College.objects.get_or_create(code=code, defaults={"fullname": fullname})
        mapping[code] = obj
        print(f"  ✓ {code:<4} {fullname}")
    return mapping


def ensure_role_groups() -> dict[str, Group]:
    """Ensure one `Group` per role; return mapping role → group."""
    return {
        role: Group.objects.get_or_create(name=role.capitalize())[0]
        for role in USER_ROLES
    }


def upsert_test_user(username: str, pwd: str) -> User:
    user, created = User.objects.get_or_create(username=username)
    if created:
        user.set_password(pwd)
        user.email = f"{username.replace('_', '.')}@tu.koba.sarl"
        user.is_staff = True
        user.save()
    return user


def content_type_map() -> dict[str, ContentType]:
    """Lazy build if you don't keep a constant in constants.py."""
    return {
        name: ContentType.objects.get(app_label="app", model=name)
        for name in OBJECT_PERM_MATRIX
    }


# ────────────────────────────────────────────────────────────────────
# Management Command
# ────────────────────────────────────────────────────────────────────


class Command(BaseCommand):
    help = "Populate dev DB with colleges, groups, test users, permissions, AY."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("\n✔  Creating superuser.\n"))
        ensure_superuser()  # dev admin

        self.stdout.write(self.style.NOTICE("⚙  Colleges"))
        code2college = populate_colleges()

        self.stdout.write(self.style.NOTICE("\n⚙  Groups"))
        role_groups = ensure_role_groups()

        self.stdout.write(self.style.NOTICE("\n⚙  Users + RoleAssignments"))
        for role in USER_ROLES:
            u = upsert_test_user(f"test_{role}", TEST_PW)
            u.groups.add(role_groups[role])
            college = code2college.get(DEFAULT_ROLE_TO_COLLEGE.get(role, ""), None)

            RoleAssignment.objects.update_or_create(
                user=u,
                role=role,
                college=college,
                defaults={"start_date": timezone.now().date(), "end_date": None},
            )
            self.stdout.write(f"  ↳ {u.username} ({role})")

        self.stdout.write(self.style.NOTICE("\n⚙  Model-level permissions"))
        ctype_map = content_type_map()

        for model_name, perm_dict in OBJECT_PERM_MATRIX.items():
            ct = ctype_map[model_name]
            for perm_name, roles in perm_dict.items():
                codename = f"{perm_name}_{model_name}"
                perm = Permission.objects.get(codename=codename, content_type=ct)
                for role in roles:
                    role_groups[role].permissions.add(perm)
            self.stdout.write(f"  ↳ {model_name} ({perm_dict.keys()})")

        self.stdout.write(self.style.NOTICE("\n⚙  Object-level college perms"))
        for ra in RoleAssignment.objects.filter(college__isnull=False):
            for perm_name, roles in OBJECT_PERM_MATRIX["college"].items():
                codename = f"{perm_name}_college"
                if ra.role in roles:
                    assign_perm(codename, ra.user, ra.college)
            self.stdout.write(f"  ↳ {perm_name} {roles}")

        self.stdout.write(self.style.NOTICE("\n⚙  Academic years"))
        populate_academic_years()

        self.stdout.write(self.style.SUCCESS("\n✔  All seed data created.\n"))
