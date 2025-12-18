"""Shared admin filters (college/department/curriculum/level)."""

from __future__ import annotations

from typing import Iterable, Sequence, TypeVar, cast

from admin_searchable_dropdown.filters import AutocompleteFilter, _get_rel_model
from django.contrib import admin
from django.core.exceptions import FieldError
from django.db.models import Manager, Model, QuerySet
from django.http import HttpRequest

from app.academics.choices import LEVEL_NUMBER
from app.academics.models import College, Curriculum, Department
from app.people.models import Student
from app.shared.types import LookUpType


ModelT = TypeVar("ModelT", bound=Model)


def _get_lookup_path(
    model: type[Model], lookup_map: Sequence[tuple[str, str]]
) -> str | None:
    """Return the lookup path for a given model based on known relations."""
    field_names = {f.name for f in model._meta.get_fields()}
    for field_name, lookup_path in lookup_map:
        if field_name in field_names:
            return lookup_path
    return None


def _filter_admin_queryset(
    model_admin: admin.ModelAdmin, request: HttpRequest, ignored_params: Iterable[str]
) -> QuerySet:
    """Apply active filters list (from the request) to the queryset."""
    qs = model_admin.get_queryset(request)
    ignored = set(ignored_params)
    ignored.update({"p", "o", "ot", "q", "_changelist_filters"})
    for param in request.GET:
        if param in ignored or param.startswith("_"):
            continue
        values = [value for value in request.GET.getlist(param) if value]
        for value in values:
            try:
                qs = qs.filter(**{param: value})
            except (FieldError, ValueError, TypeError):
                continue
    return qs


def _related_qs_for_lookup(
    model_admin: admin.ModelAdmin,
    request: HttpRequest,
    lookup_path: str | None,
    target_model: type[ModelT],
) -> QuerySet[ModelT]:
    """Should Return the queryset of related objects constrained by current filters.

    The returned queryset only contains objects reachable from the current
    changelist queryset through the provied lookup path. This keeps the
    autocomplet suggestions in sync with other active filters.
    """
    manager = cast(Manager[ModelT], getattr(target_model, "objects"))
    if not lookup_path:
        return manager.none()

    qs = _filter_admin_queryset(model_admin, request, lookup_path)
    related_ids = (
        qs.filter(**{f"{lookup_path}__isnull": False})
        .values_list(f"{lookup_path}__id", flat=True)
        .distinct()
    )
    return manager.filter(id__in=related_ids)


def _filter_queryset_by_value(
    queryset: QuerySet[ModelT], lookup_path: str | None, raw_value: str | None
) -> QuerySet[ModelT]:
    """Filter a queryset by id when a valide value is provided."""

    if not lookup_path or not raw_value:
        return queryset
    try:
        selected_id = int(raw_value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return queryset
    return queryset.filter(**{lookup_path: selected_id})


class BaseCollegeFilter(admin.SimpleListFilter):
    """Generic college filter with configurable field path."""

    title = "college"
    parameter_name = "college__id__exact"
    field_path = "college"

    def lookups(self, request, model_admin):
        colleges = College.objects.order_by("code").values_list("id", "code")
        return list(colleges)

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(**{f"{self.field_path}__id": self.value()})
        return queryset


class StudentLevelFilter(admin.SimpleListFilter):
    """Filter students by computed class level (credits-based)."""

    title = "level"
    parameter_name = "class_level"

    def lookups(self, request, model_admin):
        """All available values to filter by."""
        return [(lv.label, lv.label) for lv in LEVEL_NUMBER]

    def queryset(self, request, qs):
        """Describe how to filter the student qs."""
        level = self.value()
        if not level:
            return qs
        # Compute levels in Python; limited to current queryset ids.
        ids: list[int] = []
        for student in qs.select_related("curriculum"):
            if student.class_level == level:
                ids.append(student.id)
        return qs.filter(id__in=ids)


class ScopedAutocompleteFilter(AutocompleteFilter):
    """Shared logic for list filters with lookup-aware autocompletes."""

    title = ""
    parameter_name = ""
    field_name = ""
    use_pk_exact = False
    lookup_map: LookUpType = ()
    target_model: type[Model]

    def __init__(self, request, params, model, model_admin):
        """Resolve lookup paths and constrain autocomplete candidates."""

        self.lookup_path = _get_lookup_path(model, self.lookup_map)
        self.parameter_name = self.lookup_path or self.parameter_name
        self.field_name = (self.lookup_path or self.field_name).split("__")[-1]
        self.rel_model = (
            _get_rel_model(model, self.lookup_path) if self.lookup_path else None
        )
        self._choices_qs = _related_qs_for_lookup(
            model_admin, request, self.lookup_path, self.target_model
        )
        super().__init__(request, params, model, model_admin)

    def get_queryset_for_field(self, model, name):
        """Return limited choices when the autocomplete hits the target field."""
        if name == self.field_name:
            return self._choices_qs
        return super().get_queryset_for_field(model, name)

    def queryset(self, request, qs):
        """Filter the changelist according to the selected value."""

        return _filter_queryset_by_value(qs, self.lookup_path, self.value())
