"""Admin mixins for people."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Callable, Iterable, Protocol, TypeAlias, cast

from django import forms
from django.contrib import messages
from django.contrib import admin as dj_admin
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.db import transaction
from django.db import models
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.html import format_html_join

from app.shared.fuzzy_matching import top_name_matches
from app.people.services.merge_people import merge_people

ModelT: TypeAlias = models.Model


class _UserSyncedModel(Protocol):
    """Protocol for models that mirror username/email from a related user."""

    user: object
    username: str
    email: str


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


def _format_merge_value(value: object) -> str:
    """Return a display-friendly value for merge comparisons."""
    if value is None or value == "":
        return "-"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, time):
        return value.strftime("%H:%M:%S")
    return str(value)


def _get_attr_value(obj: ModelT, field_path: str) -> object:
    """Return a nested attribute value using Django-style paths."""
    current: object = obj
    for part in field_path.split("__"):
        current = getattr(current, part, None)
        if current is None:
            return None
    return current


def _set_attr_value(obj: ModelT, field_path: str, value: object) -> ModelT | None:
    """Set a nested attribute value and return the parent object updated."""
    current: object = obj
    parts = field_path.split("__")
    for part in parts[:-1]:
        current = getattr(current, part, None)
        if current is None:
            return None
    if not isinstance(current, models.Model):
        return None
    setattr(current, parts[-1], value)
    return current


class MergeWizardForm(forms.Form):
    """Dynamic form to select merge targets and field values."""

    def __init__(
        self,
        *args,
        candidates: Iterable[ModelT],
        merge_fields: Iterable[str],
        label_fn: Callable[[ModelT], str],
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.candidates = list(candidates)
        self.candidate_map = {str(obj.pk): obj for obj in self.candidates}
        choices = [(str(obj.pk), label_fn(obj)) for obj in self.candidates]
        self.fields["target_id"] = forms.ChoiceField(
            label="Merge target",
            choices=choices,
            widget=forms.RadioSelect,
            required=True,
        )
        for field_name in merge_fields:
            field_key = self._field_key(field_name)
            field_choices = [
                (
                    str(obj.pk),
                    f"{label_fn(obj)} -> {_format_merge_value(_get_attr_value(obj, field_name))}",
                )
                for obj in self.candidates
            ]
            self.fields[field_key] = forms.ChoiceField(
                label=self._field_label(field_name),
                choices=field_choices,
                widget=forms.RadioSelect,
                required=True,
            )

    @staticmethod
    def _field_key(field_name: str) -> str:
        """Build the form field key for a merge field path."""
        return f"field__{field_name}"

    @staticmethod
    def _field_label(field_name: str) -> str:
        """Generate a human-friendly label for a field path."""
        parts = field_name.split("__")
        return " ".join(part.replace("_", " ").title() for part in parts)


class MergeWizardMixin(dj_admin.ModelAdmin):
    """Provide a two-step merge action with per-field selection."""

    merge_template = "admin/people/merge_people.html"
    merge_fields: tuple[str, ...] = ()

    def get_actions(self, request):
        """Add the merge action without overriding existing admin actions."""
        actions = super().get_actions(request)
        if "merge_records_action" not in actions:
            # > Use unbound method to match Django action signature.
            func = getattr(self.__class__, "merge_records_action")
            description = getattr(func, "short_description", "Merge selected records")
            actions["merge_records_action"] = (
                func,
                "merge_records_action",
                description,
            )
        return actions

    def get_merge_fields(self, request) -> tuple[str, ...]:
        """Return the list of field paths to expose in the merge form."""
        return self.merge_fields

    def merge_object_label(self, obj: ModelT) -> str:
        """Return the label used for merge choices."""
        return str(obj)

    def merge_records(self, target: ModelT, sources: Iterable[ModelT]) -> None:
        """Apply merge logic to the target and sources."""
        raise NotImplementedError("merge_records must be implemented on subclasses.")

    def sync_merge_target(self, target: ModelT) -> None:
        """Sync derived fields on the merged target, when needed."""
        if hasattr(target, "_update_long_name"):
            target._update_long_name()  # type: ignore[attr-defined]
        if hasattr(target, "user") and hasattr(target, "username"):
            target_with_user = cast(_UserSyncedModel, target)
            user = getattr(target_with_user, "user", None)
            if user:
                target_with_user.username = getattr(user, "username", "")
                target_with_user.email = getattr(user, "email", "")
        if hasattr(target, "save"):
            target.save()

    def merge_records_action(self, request, queryset):
        """Action to merge selected records with a detailed selection form."""
        count = queryset.count()
        if count < 2:
            self.message_user(
                request,
                "Select at least two entries to merge.",
                level=messages.WARNING,
            )
            return
        selected_ids = request.POST.getlist(ACTION_CHECKBOX_NAME)
        candidates = queryset.filter(pk__in=selected_ids)
        merge_fields = self.get_merge_fields(request)
        form_data = request.POST if request.POST.get("apply_merge") else None
        form = MergeWizardForm(
            data=form_data,
            candidates=candidates,
            merge_fields=merge_fields,
            label_fn=self.merge_object_label,
        )
        if request.POST.get("apply_merge") and form.is_valid():
            target_id = form.cleaned_data["target_id"]
            target = candidates.get(pk=target_id)
            sources = candidates.exclude(pk=target.pk)
            source_count = sources.count()
            updated_objects: set[ModelT] = set()
            with transaction.atomic():
                # Apply selected values to the target before running merges.
                for field_name in merge_fields:
                    field_key = form._field_key(field_name)
                    selected_id = form.cleaned_data.get(field_key)
                    selected_obj = form.candidate_map.get(str(selected_id))
                    if selected_obj is None:
                        continue
                    value = _get_attr_value(selected_obj, field_name)
                    updated = _set_attr_value(target, field_name, value)
                    if updated is not None:
                        updated_objects.add(updated)
                for obj in updated_objects:
                    obj.save()
                self.merge_records(target, sources)
                self.sync_merge_target(target)
            self.message_user(
                request,
                f"Merged {source_count} record(s) into {target}.",
                level=messages.SUCCESS,
            )
            return None
        context = {
            "title": "Merge selected records",
            "objects": candidates,
            "form": form,
            "action_name": "merge_records_action",
            "action_checkbox_name": ACTION_CHECKBOX_NAME,
        }
        return TemplateResponse(request, self.merge_template, context)

    merge_records_action.short_description = "Merge selected records"  # type: ignore[attr-defined]


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
