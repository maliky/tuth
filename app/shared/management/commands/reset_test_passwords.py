"""Reset the password for users whose usernames share a prefix."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Reset all test_* users (or any prefix) to a shared password."""

    help = (
        "Reset the password for every user whose username starts with a given prefix. "
        "Default prefix is 'test_' and default password is 'PassW0rd!'."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--prefix",
            default="test_",
            help="Username prefix filter (default: %(default)s)",
        )
        parser.add_argument(
            "--password",
            default="PassW0rd!",
            help="Password to set on the matching accounts (default: %(default)s)",
        )

    def handle(self, *args, **options):
        prefix: str = options["prefix"]
        password: str = options["password"]

        User = get_user_model()
        queryset = User.objects.filter(username__startswith=prefix)
        updated = queryset.count()

        for user in queryset.iterator():
            user.set_password(password)
            user.save(update_fields=["password"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Updated {updated} user(s) with prefix '{prefix}' to password '{password}'."
            )
        )
