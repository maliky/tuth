"""App/shared/management/commands/create_test_users.py."""

from app.shared.auth.helpers import ensure_superuser
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from app.people.choices import UserRole


class Command(BaseCommand):
    """Create test users using the UserRole."""

    help = "Create test users and assign them to role groups."

    TEST_PASSWORD = "test"

    def handle(self, *args, **options):
        """Command managing the import."""
        created = []

        ensure_superuser(self)
        
        for role in UserRole:
            username = f"test_{role.value}"
            user, was_created = User.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": role.label,
                    "last_name": "Test",
                    "password": "test",
                    "email": f"{username}.test@tubmanu.edu.lr",
                },
            )
            user.set_password(self.TEST_PASSWORD)
            user.save()

            # Assign group  to user
            group, _ = Group.objects.get_or_create(name=role.label)
            user.groups.add(group)

            created.append((user.username, group.name, was_created))

        # nicely report results
        self.stdout.write(self.style.SUCCESS("Test users created or updated:"))
        for username, group_name, was_created in created:
            status = "Created" if was_created else "Updated"
            self.stdout.write(f" - {username} ({group_name}): {status}")
