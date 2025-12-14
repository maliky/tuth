"""Admin mixins for people."""

from __future__ import annotations

from django.contrib import messages
from django.db import transaction
from django.urls import reverse
from django.utils.html import format_html, format_html_join

from app.people.matching import name_similarity
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

    def possible_duplicates(self, obj):
        base_name = getattr(obj, "long_name", "") or getattr(
            getattr(obj, "staff_profile", None), "long_name", ""
        )
        # pick a comparable user and last name
        person_user = getattr(obj, "user", None) or getattr(
            getattr(obj, "staff_profile", None), "user", None
        )
        if not person_user:
            return ""

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
        rows = []
        for other in qs[:50]:
            other_name = getattr(other, "long_name", "") or getattr(
                getattr(other, "staff_profile", None), "long_name", ""
            )
            score = name_similarity(base_name, other_name)
            if score >= self.duplicate_threshold:
                label = getattr(other, "obj_id", "") or str(other.pk)
                url = reverse(
                    f"admin:{other._meta.app_label}_{other._meta.model_name}_change",
                    args=[other.pk],
                )
                rows.append((url, label, score))
        if not rows:
            return ""
        safe_rows = []
        for url, label, score in rows[:3]:
            safe_rows.append((url, label, f"{score:.2f}"))
        return format_html_join(
            ", ",
            '<a href="{}">{}</a> ({})',
            safe_rows,
        )

    possible_duplicates.short_description = "Possible duplicates"  # type: ignore[attr-defined]
