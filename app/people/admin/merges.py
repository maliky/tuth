"""A module for user mergins actions."""

from django.db import transaction


class MergeUsersMixin:
    """Admin action to merge selected auth users."""

    actions = ["merge_users_action"]

    def merge_users_action(self, request, queryset):
        count = queryset.count()
        if count < 2:
            self.message_user(
                request,
                "Select at least two users to merge.",
                level=messages.WARNING,
            )
            return
        target = queryset.order_by("id").first()
        sources = queryset.exclude(pk=target.pk)
        merged = 0
        with transaction.atomic():
            for source in sources:
                try:
                    merge_users(target, source)
                    merged += 1
                except ValueError as exc:
                    self.message_user(
                        request,
                        f"Skipping user {source} ({exc})",
                        level=messages.WARNING,
                    )
        self.message_user(
            request,
            f"Merged {merged} user(s) into {target.username}.",
            level=messages.SUCCESS,
        )
