"""Admin mixins for people."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Callable, Iterable, Protocol, TypeAlias, cast

from django import forms
from django.contrib import messages
from django.contrib import admin as dj_admin
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.core.exceptions import FieldDoesNotExist
from django.db import transaction
from django.db import models
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.html import format_html, format_html_join

from app.shared.fuzzy_matching import name_similarity
from app.people.services.merge_people import merge_people

ModelT: TypeAlias = models.Model
MergeSummaryT: TypeAlias = dict[str, int]


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


def _candidate_timestamp(obj: ModelT) -> datetime | None:
    """Return a candidate timestamp to prefer older records."""
    for attr in ("date_joined", "created_at"):
        value = getattr(obj, attr, None)
        if isinstance(value, datetime):
            return value
    return None


def _default_candidate_id(candidates: list[ModelT]) -> str | None:
    """Return the default candidate id (oldest record first)."""
    if not candidates:
        return None

    def _sort_key(obj: ModelT) -> tuple[int, datetime | int, int]:
        timestamp = _candidate_timestamp(obj)
        pk_value = getattr(obj, "pk", None) or 0
        if timestamp is not None:
            return (0, timestamp, pk_value)
        return (1, pk_value, 0)

    oldest = min(candidates, key=_sort_key)
    if not oldest.pk:
        return None
    return str(oldest.pk)


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


def _resolve_field(model: type[models.Model], field_path: str) -> models.Field | None:
    """Return the resolved Django field for a nested field path."""
    current_model = model
    parts = field_path.split("__")
    for index, part in enumerate(parts):
        try:
            field = current_model._meta.get_field(part)
        except FieldDoesNotExist:
            return None
        if not isinstance(field, models.Field):
            return None
        if index < len(parts) - 1:
            related = getattr(field, "remote_field", None)
            if not related:
                return None
            current_model = related.model
        else:
            return field
    return None


def _build_unique_placeholder(
    field: models.Field, value: object, obj_pk: object
) -> object:
    """Return a placeholder value that frees a unique field."""
    if not isinstance(value, str):
        return value
    suffix = f"_merged_{obj_pk}"
    max_length = getattr(field, "max_length", None)
    if not max_length:
        return f"{value}{suffix}" if value else f"merged{suffix}"
    if max_length <= len(suffix):
        return suffix[-max_length:]
    base_value = value or "merged"
    keep_len = max_length - len(suffix)
    return f"{base_value[:keep_len]}{suffix}"


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
        default_candidate_id = _default_candidate_id(self.candidates)
        choices = [(str(obj.pk), label_fn(obj)) for obj in self.candidates]
        self.fields["target_id"] = forms.ChoiceField(
            label="Merge target",
            choices=choices,
            widget=forms.RadioSelect,
            required=True,
        )
        if default_candidate_id:
            # > Default to the oldest record to preserve existing values.
            self.fields["target_id"].initial = default_candidate_id
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
            if default_candidate_id:
                # > Default to older record values for sparse fields.
                self.fields[field_key].initial = default_candidate_id

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

    def merge_records(
        self, target: ModelT, sources: Iterable[ModelT]
    ) -> MergeSummaryT | None:
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
            original_values = {
                field_name: _get_attr_value(target, field_name)
                for field_name in merge_fields
            }
            updated_objects: set[ModelT] = set()
            unique_updates: list[tuple[str, ModelT, models.Field, object]] = []
            self._merge_original_values = original_values
            self._merge_request = request
            try:
                with transaction.atomic():
                    # Apply selected values to the target before running merges.
                    for field_name in merge_fields:
                        field_key = form._field_key(field_name)
                        selected_id = form.cleaned_data.get(field_key)
                        selected_obj = form.candidate_map.get(str(selected_id))
                        if selected_obj is None:
                            continue
                        value = _get_attr_value(selected_obj, field_name)
                        field = _resolve_field(type(target), field_name)
                        if (
                            field
                            and (field.unique or field.primary_key)
                            and selected_obj.pk
                            and selected_obj.pk != target.pk
                        ):
                            unique_updates.append(
                                (field_name, selected_obj, field, value)
                            )
                        updated = _set_attr_value(target, field_name, value)
                        if updated is not None:
                            updated_objects.add(updated)
                    # > Free unique values on source rows before saving the target.
                    for field_name, selected_obj, field, value in unique_updates:
                        placeholder = _build_unique_placeholder(
                            field, value, selected_obj.pk
                        )
                        updated = _set_attr_value(selected_obj, field_name, placeholder)
                        if updated is not None:
                            updated.save()
                    for obj in updated_objects:
                        obj.save()
                    merge_summary = self.merge_records(target, sources)
                    self.sync_merge_target(target)
            finally:
                self._merge_original_values = {}
                self._merge_request = None
            merged_total = source_count
            if isinstance(merge_summary, dict):
                merged_total = merge_summary.get("merged", source_count)
            self.message_user(
                request,
                f"Merged {merged_total} record(s) into {target}.",
                level=messages.SUCCESS,
            )
            if isinstance(merge_summary, dict):
                skipped_incompatible = merge_summary.get("skipped_incompatible", 0)
                if skipped_incompatible:
                    self.message_user(
                        request,
                        f"Skipped {skipped_incompatible} incompatible selection(s).",
                        level=messages.WARNING,
                    )
                skipped_invoices = merge_summary.get("skipped_invoices", 0)
                if skipped_invoices:
                    self.message_user(
                        request,
                        f"Skipped {skipped_invoices} selection(s) with invoices.",
                        level=messages.WARNING,
                    )
                credit_hours_conflicts = merge_summary.get("credit_hours_conflicts", 0)
                if credit_hours_conflicts:
                    self.message_user(
                        request,
                        (
                            "Credit hours differ on "
                            f"{credit_hours_conflicts} selection(s)."
                        ),
                        level=messages.WARNING,
                    )
                is_required_conflicts = merge_summary.get("is_required_conflicts", 0)
                if is_required_conflicts:
                    self.message_user(
                        request,
                        (
                            "Required flag differs on "
                            f"{is_required_conflicts} selection(s)."
                        ),
                        level=messages.WARNING,
                    )
                is_elective_conflicts = merge_summary.get("is_elective_conflicts", 0)
                if is_elective_conflicts:
                    self.message_user(
                        request,
                        (
                            "Elective flag differs on "
                            f"{is_elective_conflicts} selection(s)."
                        ),
                        level=messages.WARNING,
                    )
                sections_merged = merge_summary.get("sections_merged", 0)
                if sections_merged:
                    self.message_user(
                        request,
                        f"Merged {sections_merged} conflicting section(s).",
                        level=messages.INFO,
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
    duplicate_count_field_name = "duplicate_count_link"

    def get_queryset(self, request):
        """Attach duplicate ordering and optional duplicate filters."""
        # > Mypy: mixin expects ModelAdmin.get_queryset in the MRO.
        qs = super().get_queryset(request)  # type: ignore[misc]
        # > Cache per-request duplicate metrics for list display and ordering.
        self._duplicate_score_cache: dict[int, float] = {}
        self._duplicate_count_cache: dict[int, int] = {}

        dup_target = request.GET.get("dups_for")
        if dup_target:
            target = qs.filter(pk=dup_target).first()
            if target:
                dup_ids = {target.pk}
                dup_ids.update(
                    other.pk for other, _ in self._duplicate_matches(target) if other.pk
                )
                qs = qs.filter(pk__in=dup_ids)

        if self._should_order_by_duplicate_score(request):
            score_map = self._duplicate_score_map(qs)
            when_statements = [
                models.When(pk=pk, then=models.Value(score))
                for pk, score in score_map.items()
            ]
            qs = qs.annotate(
                duplicate_score_sort=models.Case(
                    *when_statements,
                    default=models.Value(0.0),
                    output_field=models.FloatField(),
                )
            )
        if self._should_order_by_duplicate_count(request):
            count_map = self._duplicate_count_map(qs)
            when_statements = [
                models.When(pk=pk, then=models.Value(count))
                for pk, count in count_map.items()
            ]
            qs = qs.annotate(
                duplicate_count_sort=models.Case(
                    *when_statements,
                    default=models.Value(0),
                    output_field=models.IntegerField(),
                )
            )
        return qs

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

    def _duplicate_candidates(self, obj) -> tuple[str, models.QuerySet]:
        """Return base name and candidate queryset used for duplicate checks."""
        base_name = self._get_long_name(obj)
        # pick a comparable user and last name
        person_user = getattr(obj, "user", None) or getattr(
            getattr(obj, "staff_profile", None), "user", None
        )
        if not person_user:
            return base_name, obj.__class__.objects.none()
        qs = self._get_candidates(obj, person_user)
        return base_name, qs

    def _duplicate_matches(self, obj) -> list[tuple[ModelT, float]]:
        """Return all matches meeting the similarity threshold."""
        base_name, qs = self._duplicate_candidates(obj)
        if not base_name:
            return []
        matches: list[tuple[ModelT, float]] = []
        for other in qs[:50]:
            other_name = self._get_long_name(other)
            score = name_similarity(base_name, other_name)
            if score >= self.duplicate_threshold:
                matches.append((other, score))
        matches.sort(key=lambda item: item[1], reverse=True)
        return matches

    def _duplicate_score_value(self, obj) -> float:
        """Return the best match score for the object."""
        cache = getattr(self, "_duplicate_score_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._duplicate_score_cache = cache
        score_cache = cast(dict[int, float], cache)
        if obj.pk in score_cache:
            return score_cache[obj.pk]
        matches = self._duplicate_matches(obj)
        score = matches[0][1] if matches else 0.0
        if obj.pk:
            score_cache[obj.pk] = score
        return score

    def _duplicate_count_value(self, obj) -> int:
        """Return the number of potential duplicates for the object."""
        cache = getattr(self, "_duplicate_count_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._duplicate_count_cache = cache
        count_cache = cast(dict[int, int], cache)
        if obj.pk in count_cache:
            return count_cache[obj.pk]
        count = len(self._duplicate_matches(obj))
        if obj.pk:
            count_cache[obj.pk] = count
        return count

    def _duplicate_score_map(self, queryset: models.QuerySet) -> dict[int, float]:
        """Build a map of PKs to best duplicate score."""
        score_map: dict[int, float] = {}
        for obj in queryset:
            if not obj.pk:
                continue
            score_map[obj.pk] = self._duplicate_score_value(obj)
        self._duplicate_score_cache = score_map
        return score_map

    def _duplicate_count_map(self, queryset: models.QuerySet) -> dict[int, int]:
        """Build a map of PKs to duplicate counts."""
        count_map: dict[int, int] = {}
        for obj in queryset:
            if not obj.pk:
                continue
            count_map[obj.pk] = self._duplicate_count_value(obj)
        self._duplicate_count_cache = count_map
        return count_map

    def _should_order_by_duplicate_score(self, request) -> bool:
        """Return True when ordering by the duplicate score column."""
        ordering = request.GET.get("o", "")
        if not ordering:
            return False
        admin_self = cast(dj_admin.ModelAdmin, self)
        list_display = list(admin_self.get_list_display(request))
        if self.duplicate_field_name not in list_display:
            return False
        duplicate_index = list_display.index(self.duplicate_field_name) + 1
        order_fields = [
            part.lstrip("-") for part in ordering.split(",") if part.lstrip("-").isdigit()
        ]
        return str(duplicate_index) in order_fields

    def _should_order_by_duplicate_count(self, request) -> bool:
        """Return True when ordering by the duplicate count column."""
        ordering = request.GET.get("o", "")
        if not ordering:
            return False
        admin_self = cast(dj_admin.ModelAdmin, self)
        list_display = list(admin_self.get_list_display(request))
        if self.duplicate_count_field_name not in list_display:
            return False
        duplicate_index = list_display.index(self.duplicate_count_field_name) + 1
        order_fields = [
            part.lstrip("-") for part in ordering.split(",") if part.lstrip("-").isdigit()
        ]
        return str(duplicate_index) in order_fields

    def possible_duplicates(self, obj):
        """Return a list of links to possible duplicates based on name similarity."""
        # > What is missing here is to take in account ambiguous duplicates

        matches = self._duplicate_matches(obj)[:3]
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
    possible_duplicates.admin_order_field = "duplicate_score_sort"  # type: ignore[attr-defined]

    @dj_admin.display(description="Duplicates")
    def duplicate_count_link(self, obj):
        """Return a link to the duplicate-filtered changelist."""
        count = self._duplicate_count_value(obj)
        if not count:
            return "0"
        url = reverse(f"admin:{obj._meta.app_label}_{obj._meta.model_name}_changelist")
        return format_html('<a href="{}?dups_for={}">{}</a>', url, obj.pk, count)

    duplicate_count_link.admin_order_field = "duplicate_count_sort"  # type: ignore[attr-defined]
