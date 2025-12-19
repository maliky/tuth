"""Admin mixins for people."""

from __future__ import annotations

from django.contrib import messages
from django.db import transaction
from django.urls import reverse
from django.utils.html import format_html, format_html_join

from app.people.matching import top_name_matches
from app.people.services.merge_people import merge_people, merge_users
from django.contrib.auth import get_user_model
from django.contrib import admin as dj_admin

User = get_user_model()


class MergePeopleMixin(dj_admin.ModelAdmin):
    """Shared admin action to merge selected people into the first selected."""

    actions: list[str] = ["merge_people_action"]

    def merge_people_action(self, request, queryset):
        count = queryset.count()
        if count < 2:
            self.message_user(
                request,
                "Select at least two entries to merge.",
                level=messages.WARNING,
            )
            return
        target = queryset.order_by("id").first()
        sources = queryset.exclude(pk=target.pk)
        merged = 0
        with transaction.atomic():
            for source in sources:
                merge_people(target, source)
                merged += 1
        self.message_user(
            request,
            f"Merged {merged} record(s) into {target}.",
            level=messages.SUCCESS,
        )


class DuplicatePreviewMixin:
    """Adds a computed column with potential duplicates."""

    duplicate_threshold = 0.9
    duplicate_field_name = "possible_duplicates"

    def _get_long_name(self, obj):
        """Get the long name of an object if it exists. or the staff_profile.long_name."""
        return getattr(obj, "long_name", "") or getattr(
            getattr(obj, "staff_profile", None), "long_name", ""
        )

    def _get_candidates(self, obj, person_user):
        """Get a queryset of user or staff with same last name as person_user."""
        if hasattr(obj, "user"):
            qs = obj.__class__.objects.exclude(pk=obj.pk).filter(
                user__last_name__iexact=person_user.last_name
            )
        elif hasattr(obj, "staff_profile"):
            qs = obj.__class__.objects.exclude(pk=obj.pk).filter(
                staff_profile__user__last_name__iexact=person_user.last_name
            )
        else:
            qs = obj.__class__.objects.none()
        return qs

    def possible_duplicates(self, obj):
        """Return a list of links to possible duplicates based on name similarity."""
        # > What is missing here is to take in account ambiguous duplicates

        base_name = self._get_long_name(obj)

        # pick a comparable user and last name
        person_user = getattr(obj, "user", None) or getattr(
            getattr(obj, "staff_profile", None), "user", None
        )
        if not person_user:
            return ""
        qs = self._get_candidates(obj, person_user)

        matches = top_name_matches(
            base_name,
            qs[:50],
            token_fn=self._get_long_name,
            threshold=self.duplicate_threshold,
            limit=3,
        )
        if not matches:
            return ""
        safe_rows = []
        for other, score in matches:
            label = getattr(other, "obj_id", "") or str(other.pk)
            url = reverse(
                f"admin:{other._meta.app_label}_{other._meta.model_name}_change",
                args=[other.pk],
            )
            safe_rows.append((url, label, f"{score:.2f}"))
        return format_html_join(
            ", ",
            '<a href="{}">{}</a> ({})',
            safe_rows,
        )

    possible_duplicates.short_description = "Possible duplicates"  # type: ignore[attr-defined]
