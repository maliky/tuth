"""App/shared/management/commands/create_test_users.py."""

from datetime import date
from app.people.models.role_assignment import RoleAssignment
from app.people.models.staffs import Faculty
from app.shared.auth.helpers import ensure_superuser
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from app.shared.auth.perms import TEST_PW, UserRole


class Command(BaseCommand):
    """Create test users using the UserRole."""

    help = "Create test users and assign them to role groups."

    TEST_PASSWORD = "test"

    def handle(self, *args, **options):
        """Command managing the import."""
        created = []

        ensure_superuser(self)

        for user_role in UserRole:
            username = f"test_{user_role.value.code}"
            Person = user_role.value.model
            person, was_created = Person.objects.get_or_create(  # type: ignore[attr-defined]
                defaults={
                    "first_name": user_role.value.label,
                    "last_name": "Person",
                    "password": TEST_PW,
                    "email": f"{username}@tubmanu.edu.lr",
                },
                username=username,
            )

            # Assign group to user and role assignment
            group, _ = Group.objects.get_or_create(name=user_role.value.group)
            if isinstance(person, Faculty):
                _user = person.staff_profile.user
            else:
                _user = person.user

            _user.groups.add(group)
            RoleAssignment.objects.get_or_create(
                user=_user,
                role=user_role.group,
                start_date=date.today(),
                college=user_role.value.college,
            )

            created.append((person.username, group.name, was_created))  # type: ignore[attr-defined]

        # nicely report results
        self.stdout.write(self.style.SUCCESS("Test users created or updated:"))
        for username, group.name, was_created in created:
            status = "Created" if was_created else "Updated"
            self.stdout.write(f" - {username} ({group.name}): {status}")


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
