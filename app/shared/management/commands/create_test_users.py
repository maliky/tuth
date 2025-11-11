"""App/shared/management/commands/create_test_users.py."""

from datetime import date
from typing import Any, cast

from app.academics.models.college import College
from app.people.utils import mk_password
from django.apps import apps
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import models as django_models

from app.people.models.role_assignment import RoleAssignment
from app.people.models.faculty import Faculty
from app.shared.auth.helpers import ensure_superuser
from app.shared.auth.perms import APP_MODELS, UserRole


class Command(BaseCommand):
    """Create test users using the UserRole."""

    help = "Create test users and assign them to role groups."

    def handle(self, *args, **options):
        """Command managing the import."""
        created = []
        User.objects.filter(username__startswith="test_").delete()

        ensure_superuser(self)

        for user_role in UserRole:
            username = f"test_{user_role.value.code}"
            person_model = cast(Any, user_role.value.model)

            person, was_created = person_model.objects.get_or_create(
                defaults={
                    "first_name": user_role.value.label,
                    "last_name": "Person",
                    "email": f"{username}@tubmanu.edu.lr",
                },
                username=username,
            )  # type: ignore[attr-defined]
            _user = (
                person.staff_profile.user if isinstance(person, Faculty) else person.user
            )

            pwd = mk_password(_user.first_name, _user.last_name)
            _user.set_password(pwd)
            _user.save(update_fields=["password"])
            college = None
            if user_role.value.default_college:
                college, _ = College.objects.get_or_create(
                    code=user_role.value.default_college
                )

            group = user_role.value.group
            _user.groups.add(group)
            RoleAssignment.objects.get_or_create(
                user=_user, group=group, start_date=date.today(), college=college
            )
            created.append(
                (person.username, group.name, was_created)
            )  # type: ignore[attr-defined]
            # log
            status = "Created" if was_created else "Updated"
            self.stdout.write(f" - {_user} ({group}): {status} with pwd {pwd}")

        # nicely report results
        self.stdout.write(self.style.SUCCESS("Test users created or updated:"))


def get_app_label(model):
    """Return the app label for the model based on perms.APP_MODELS."""
    for app_label, models in APP_MODELS.items():
        if model in models:
            return app_label
    raise Exception(f"model {model}  not found in perms.APP_MODELS")


def sync_role_group(role_code: str, rights: dict[str, list[str]]) -> Group:
    """Ensure a Django group exists for this role and sync its permissions."""
    grp, _ = Group.objects.get_or_create(name=role_code.capitalize())
    perms = []

    for action, models in rights.items():
        for model in models:
            app_label = get_app_label(model)
            model_cls = apps.get_model(app_label, model)
            ct = ContentType.objects.get_for_model(model_cls)
            codename = f"{action}_{model}"
            perm, _ = Permission.objects.get_or_create(codename=codename, content_type=ct)
            perms.append(perm)

    grp.permissions.set(perms)
    return grp
