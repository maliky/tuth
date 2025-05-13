# app/management/commands/populate_initial_data.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group, Permission
from django.db import transaction
from django.utils import timezone
from guardian.shortcuts import assign_perm
from django.contrib.contenttypes.models import ContentType


# from guardian.shortcuts import assign_perm

from app.constants import (
    COLLEGE_CHOICES,
    USER_ROLES,
    OBJECT_PERM_MATRIX,
    TEST_PW,
    DEFAULT_ROLE_TO_COLLEGE,
)
from app.models import College, RoleAssignment

# ---------- helper maps ----------


class Command(BaseCommand):
    help = "Populate development DB with colleges, groups, roles and test users."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("⚙  Populating colleges…"))

        CONTENT_TYPE_MAP = {
            model_name: ContentType.objects.get(app_label="app", model=model_name)
            for model_name in OBJECT_PERM_MATRIX
        }

        code_to_college = {}
        for code, fullname in COLLEGE_CHOICES:
            obj, _ = College.objects.get_or_create(
                code=code, defaults={"fullname": fullname}
            )
            code_to_college[code] = obj
            self.stdout.write(f"  ✓ {code} ({fullname})")

        self.stdout.write(self.style.NOTICE("\n⚙  Populating groups (one per role)…"))
        role_groups = {
            role: Group.objects.get_or_create(name=role.capitalize())[0]
            for role in USER_ROLES
        }

        self.stdout.write(
            self.style.NOTICE("\n⚙  Populating users and role-assignments…")
        )
        for role in USER_ROLES:
            username = f"test_{role}"
            user, created = User.objects.get_or_create(username=username)
            if created:
                user.set_password(TEST_PW)
                user.email = f"{username.replace('_', '.')}@tu.koba.sarl"
                user.is_staff = True
                user.save()
                self.stdout.write(self.style.SUCCESS(f"  + user '{username}' created"))

            else:
                self.stdout.write(f"  = user '{username}' already exists")

            # add to group (makes permission assignment easier later)
            user.groups.add(role_groups[role])

            # optional college assignment
            college = None
            if role in DEFAULT_ROLE_TO_COLLEGE:
                college = code_to_college[DEFAULT_ROLE_TO_COLLEGE[role]]

            # create / update RoleAssignment
            RoleAssignment.objects.update_or_create(
                user=user,
                role=role,
                college=college,
                defaults={"start_date": timezone.now().date(), "end_date": None},
            )

        self.stdout.write(self.style.SUCCESS("\n✔  Initial data population complete.\n"))

        for model_name, perms in OBJECT_PERM_MATRIX.items():
            content_type = CONTENT_TYPE_MAP[model_name]

            for perm_codename, roles in perms.items():
                perm = Permission.objects.get(
                    codename=perm_codename, content_type=content_type
                )
                for role in roles:
                    group = role_groups[role]
                    group.permissions.add(perm)
                    self.stdout.write(self.style.SUCCESS(f"Permission {perm} to {group}"))

        # Object-level permission assignment for all roles linked to a specific college
        for ra in RoleAssignment.objects.filter(college__isnull=False):
            user = ra.user
            college = ra.college
            role = ra.role
            for perm_codename, roles in OBJECT_PERM_MATRIX["college"].items():
                if role in roles:
                    assign_perm(perm_codename, user, college)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Object perm '{perm_codename}' assigned to '{user}' for '{college}'"
                        )
                    )

        self.stdout.write(
            self.style.SUCCESS("\n✔ Guardian object-level permissions assigned.\n")
        )


# +END_SRC
