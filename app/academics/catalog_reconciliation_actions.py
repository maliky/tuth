"""Action classifiers for catalog reconciliation rows."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypeAlias

from app.academics.reconciliation_io import RowT

CompareFieldsT: TypeAlias = Sequence[tuple[str, str, str]]


def _sum_usage(rows: list[RowT]) -> int:
    """Return summed usage_total values from current rows."""
    return sum(int(row.get("usage_total") or 0) for row in rows)


def _changes(current: RowT, org: RowT, fields: CompareFieldsT) -> str:
    """Return field names whose current/org values differ."""
    changed: list[str] = []
    for label, current_field, org_field in fields:
        current_value = (current.get(current_field) or "").strip()
        org_value = (org.get(org_field) or "").strip()
        if current_value != org_value:
            changed.append(label)
    return ",".join(changed)


def _current_org_state(current_rows: list[RowT], org_rows: list[RowT]) -> str:
    """Classify key presence before detailed action decisions."""
    if current_rows and org_rows:
        return "current_and_org"
    if org_rows:
        return "org_only"
    return "current_only"


def _duplicate_note(current_rows: list[RowT], org_rows: list[RowT]) -> str:
    """Return duplicate-key diagnostics when a key is not one-to-one."""
    notes: list[str] = []
    if len(current_rows) > 1:
        notes.append(f"current duplicates={len(current_rows)}")
    if len(org_rows) > 1:
        notes.append(f"org duplicates={len(org_rows)}")
    return "; ".join(notes)


def course_action(current_rows: list[RowT], org_rows: list[RowT]) -> tuple[str, str, str]:
    """Return category, action, and notes for a course key."""
    state = _current_org_state(current_rows, org_rows)
    usage = _sum_usage(current_rows)
    if state == "org_only":
        return state, "create_course", "new org catalog course"
    if state == "current_only":
        if usage:
            return (
                state,
                "preserve_current_course_for_history",
                "student/finance data exists",
            )
        return state, "candidate_archive_after_review", "not present in org ground truth"
    duplicate_note = _duplicate_note(current_rows, org_rows)
    if duplicate_note:
        return "duplicate_key", "manual_review", duplicate_note
    changed = _changes(
        current_rows[0],
        org_rows[0],
        (
            ("title", "course_title", "course_title"),
            ("description", "description", "description"),
        ),
    )
    if changed:
        return "metadata_diff", "update_course_metadata", f"changed={changed}"
    return "matched", "keep", ""


def curriculum_action(
    current_rows: list[RowT], org_rows: list[RowT]
) -> tuple[str, str, str]:
    """Return category, action, and notes for a curriculum key."""
    state = _current_org_state(current_rows, org_rows)
    usage = _sum_usage(current_rows)
    if state == "org_only":
        return state, "create_curriculum_pending", "new org curriculum"
    if state == "current_only":
        if usage:
            return (
                state,
                "preserve_current_curriculum_for_students",
                "student data exists",
            )
        return state, "candidate_archive_after_review", "not present in org ground truth"
    duplicate_note = _duplicate_note(current_rows, org_rows)
    if duplicate_note:
        return "duplicate_key", "manual_review", duplicate_note
    changed = _changes(
        current_rows[0],
        org_rows[0],
        (
            ("college", "college_code", "curriculum_college_code"),
            ("long_name", "long_name", "long_name"),
        ),
    )
    if changed and usage:
        return "metadata_diff", "review_referenced_curriculum", f"changed={changed}"
    if changed:
        return "metadata_diff", "update_curriculum_metadata", f"changed={changed}"
    return (
        "matched",
        "keep",
        "org status remains advisory; do not auto-downgrade approved rows",
    )


def curriculum_course_action(
    current_rows: list[RowT], org_rows: list[RowT]
) -> tuple[str, str, str]:
    """Return category, action, and notes for a curriculum-course key."""
    state = _current_org_state(current_rows, org_rows)
    usage = _sum_usage(current_rows)
    if state == "org_only":
        return state, "create_curriculum_course", "new org program course"
    if state == "current_only":
        if usage:
            return (
                state,
                "preserve_current_curriculum_course_for_history",
                "student/finance data exists",
            )
        return state, "candidate_archive_after_review", "not present in org program"
    duplicate_note = _duplicate_note(current_rows, org_rows)
    if duplicate_note:
        return "duplicate_key", "manual_review", duplicate_note
    changed = _changes(
        current_rows[0],
        org_rows[0],
        (
            ("credit_hours", "credit_hours", "credit_hours"),
            ("year_number", "year_number", "year_number"),
            ("semester_number", "semester_number", "semester_number"),
            ("level_number", "level_number", "level_number"),
            ("is_required", "is_required", "is_required"),
        ),
    )
    if changed and usage:
        return (
            "metadata_diff",
            "review_referenced_curriculum_course",
            f"changed={changed}",
        )
    if changed:
        return "metadata_diff", "update_curriculum_course_metadata", f"changed={changed}"
    return "matched", "keep", ""
