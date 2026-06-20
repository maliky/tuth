"""PDF layout helpers for registrar transcript rendering."""

from __future__ import annotations

from math import ceil
from typing import TypeAlias, TypedDict

from app.website.services.transcript_types import (
    TranscriptLayoutKeyT,
    TranscriptTermGroupT,
    normalize_transcript_layout,
)

TermColumnT: TypeAlias = list[TranscriptTermGroupT]


class TranscriptPdfLayoutT(TypedDict):
    """Display knobs consumed only by the WeasyPrint transcript template."""

    attempted_label: str
    css_class: str
    earned_label: str
    grade_label: str
    page_margin: str
    points_label: str
    term_columns: list[TermColumnT]


def _term_weight(group: TranscriptTermGroupT) -> int:
    """Return an approximate display weight for an indivisible term block."""
    return len(group["rows"]) + 3


def split_term_groups_for_columns(
    groups: list[TranscriptTermGroupT],
) -> list[TermColumnT]:
    """Split transcript terms into two balanced columns without breaking a term."""
    if not groups:
        return [[], []]
    if len(groups) == 1:
        return [groups, []]

    target_weight = ceil(sum(_term_weight(group) for group in groups) / 2)
    left: TermColumnT = []
    right: TermColumnT = []
    current_weight = 0
    for group in groups:
        group_weight = _term_weight(group)
        if left and current_weight + group_weight > target_weight:
            right.append(group)
            continue
        left.append(group)
        current_weight += group_weight
    if not right and len(left) > 1:
        right.insert(0, left.pop())
    return [left, right]


def transcript_pdf_layout(
    layout_key: TranscriptLayoutKeyT,
    groups: list[TranscriptTermGroupT],
) -> TranscriptPdfLayoutT:
    """Return reference-style PDF layout settings for one transcript."""
    normalized_key = normalize_transcript_layout(layout_key)
    if normalized_key == "landscape":
        return {
            "attempted_label": "Att.",
            "css_class": "pdf-layout-landscape-two",
            "earned_label": "Earned",
            "grade_label": "Grade",
            "page_margin": "10mm 10mm 15.5mm",
            "points_label": "Qual.",
            "term_columns": split_term_groups_for_columns(groups),
        }
    return {
        "attempted_label": "Att",
        "css_class": "pdf-layout-portrait-two",
        "earned_label": "Ern",
        "grade_label": "Gr.",
        "page_margin": "11.5mm 11.5mm 18.5mm",
        "points_label": "Pts",
        "term_columns": split_term_groups_for_columns(groups),
    }


__all__ = [
    "TranscriptPdfLayoutT",
    "split_term_groups_for_columns",
    "transcript_pdf_layout",
]
