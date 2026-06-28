"""Helpers for academic-career scoped views and links."""

from __future__ import annotations

from typing import Iterable, Literal, TypeAlias
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.db.models import QuerySet
from django.http import QueryDict

from app.academics.choices import AcademicCareer

CAREER_ALL = "all"
CAREER_QUERY_PARAM = "academic_career"
CareerModeT: TypeAlias = Literal["undergraduate", "graduate", "all"]


def normalize_academic_career(
    raw_value: object,
    *,
    default: CareerModeT = "graduate",
) -> CareerModeT:
    """Return a valid career scope, defaulting to graduate records."""
    value = str(raw_value or "").strip().lower()
    allowed = {
        AcademicCareer.UNDERGRADUATE.value,
        AcademicCareer.GRADUATE.value,
        CAREER_ALL,
    }
    if value in allowed:
        return value  # type: ignore[return-value]
    return default


def selected_academic_career(params: QueryDict) -> CareerModeT:
    """Return selected career from request params."""
    return normalize_academic_career(params.get(CAREER_QUERY_PARAM))


def academic_career_label(value: CareerModeT) -> str:
    """Return display label for one career selector option."""
    if value == CAREER_ALL:
        return "All careers"
    if value == AcademicCareer.UNDERGRADUATE.value:
        return AcademicCareer.UNDERGRADUATE.label
    return AcademicCareer.GRADUATE.label


def academic_career_theme_class(value: object) -> str:
    """Return the portal theme class for a selected academic career."""
    if str(value or "") == AcademicCareer.GRADUATE.value:
        return "portal-theme-graduate"
    return ""


def career_filter_options(selected: CareerModeT) -> list[dict[str, object]]:
    """Return selector options with graduate first."""
    return [
        {
            "value": AcademicCareer.GRADUATE.value,
            "label": AcademicCareer.GRADUATE.label,
            "selected": selected == AcademicCareer.GRADUATE.value,
        },
        {
            "value": AcademicCareer.UNDERGRADUATE.value,
            "label": AcademicCareer.UNDERGRADUATE.label,
            "selected": selected == AcademicCareer.UNDERGRADUATE.value,
        },
        {
            "value": CAREER_ALL,
            "label": "All",
            "selected": selected == CAREER_ALL,
        },
    ]


def filter_by_academic_career(
    queryset: QuerySet,
    field_path: str,
    selected: CareerModeT,
) -> QuerySet:
    """Filter a queryset by career unless the broad all scope is selected."""
    if selected == CAREER_ALL:
        return queryset
    return queryset.filter(**{field_path: selected}).distinct()


def career_hidden_fields(
    params: QueryDict,
    *,
    exclude: Iterable[str] = (),
) -> list[dict[str, str]]:
    """Return GET params to preserve as hidden fields around career forms."""
    ignored = {CAREER_QUERY_PARAM, *exclude}
    return [
        {"name": key, "value": value}
        for key, values in params.lists()
        if key not in ignored
        for value in values
    ]


def append_career_query(url: str, selected: CareerModeT) -> str:
    """Return a URL with the selected academic career query parameter."""
    parsed = urlsplit(url)
    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key != CAREER_QUERY_PARAM
    ]
    query_pairs.append((CAREER_QUERY_PARAM, selected))
    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlencode(query_pairs),
            parsed.fragment,
        )
    )


def career_selector_context(
    params: QueryDict,
    *,
    action_url: str,
    exclude: Iterable[str] = (),
) -> dict[str, object]:
    """Return context for a shared academic-career selector."""
    selected = selected_academic_career(params)
    return {
        "action_url": action_url,
        "param_name": CAREER_QUERY_PARAM,
        "selected": selected,
        "selected_label": academic_career_label(selected),
        "options": career_filter_options(selected),
        "hidden_fields": career_hidden_fields(params, exclude=exclude),
    }


__all__ = [
    "CAREER_ALL",
    "CAREER_QUERY_PARAM",
    "CareerModeT",
    "academic_career_label",
    "academic_career_theme_class",
    "append_career_query",
    "career_filter_options",
    "career_hidden_fields",
    "career_selector_context",
    "filter_by_academic_career",
    "normalize_academic_career",
    "selected_academic_career",
]
