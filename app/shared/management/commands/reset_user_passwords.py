"""Reset Django user passwords in bulk with explicit exclusions."""

from __future__ import annotations

from typing import cast

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    """Reset selected user passwords while preserving excluded accounts."""

    help = "Reset passwords for all users except explicitly excluded usernames."

    def add_arguments(self, parser) -> None:
        """Add command-line options."""
        parser.add_argument(
            "--password",
            default="PassW0rd!",
            help="Password to set on matching accounts.",
        )
        parser.add_argument(
            "--exclude",
            action="append",
            default=[],
            help="Username to leave unchanged. May be passed more than once.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report how many accounts would be updated without writing changes.",
        )

    def handle(self, *args: object, **options: object) -> None:
        """Reset target user passwords and verify excluded accounts stay unchanged."""
        password = cast(str, options["password"])
        exclude_usernames = cast(list[str], options["exclude"])
        dry_run = bool(options["dry_run"])
        User = get_user_model()
        target_qs = User.objects.exclude(username__in=exclude_usernames)
        excluded_before = dict(
            User.objects.filter(username__in=exclude_usernames).values_list(
                "username",
                "password",
            )
        )
        target_count = target_qs.count()
        if dry_run:
            self.stdout.write(
                f"Would update {target_count} user(s); "
                f"excluded={','.join(exclude_usernames) or '(none)'}."
            )
            return

        password_hash = make_password(password)
        if not check_password(password, password_hash):
            raise CommandError("Generated password hash failed verification.")

        with transaction.atomic():
            updated = target_qs.update(password=password_hash)

        excluded_after = dict(
            User.objects.filter(username__in=exclude_usernames).values_list(
                "username",
                "password",
            )
        )
        changed_excluded = [
            username
            for username, previous_hash in excluded_before.items()
            if excluded_after.get(username) != previous_hash
        ]
        if changed_excluded:
            raise CommandError(
                "Excluded user password changed: " + ", ".join(changed_excluded)
            )
        wrong_hash_count = (
            User.objects.exclude(username__in=exclude_usernames)
            .exclude(password=password_hash)
            .count()
        )
        if wrong_hash_count:
            raise CommandError(
                f"{wrong_hash_count} target user(s) did not receive the new hash."
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Updated {updated} user(s); "
                f"excluded={','.join(exclude_usernames) or '(none)'}."
            )
        )
