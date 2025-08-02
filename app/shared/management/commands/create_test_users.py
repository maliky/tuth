"""App/shared/management/commands/create_test_users.py."""

from app.shared.auth.helpers import ensure_superuser
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from app.shared.auth.perms import UserRole


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
                username=username,
                defaults={
                    "first_name": user_role.value.label,
                    "last_name": "Person",
                    "password": self.TEST_PASSWORD,
                    "email": f"{username}@tubmanu.edu.lr",
                },
            )
            person.set_password(self.TEST_PASSWORD)
            person.save()

            # Assign group  to user
            group, _ = Group.objects.get_or_create(name=user_role.value.code)
            person.groups.add(group)

            created.append((Person.username, group.name, was_created))  # type: ignore[attr-defined]

        # nicely report results
        self.stdout.write(self.style.SUCCESS("Test users created or updated:"))
        for username, group_name, was_created in created:
            status = "Created" if was_created else "Updated"
            self.stdout.write(f" - {username} ({group_name}): {status}")
