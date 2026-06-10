"""Approved course-alias transforms for source-truth import outputs."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import TypeAlias

from app.shared.course_wrangling import course_key, split_course_code
from app.shared.source_truth.io import RowT, read_rows
from app.timetable.utils import normalize_academic_year

RowsT: TypeAlias = list[RowT]
CourseAliasMapT: TypeAlias = dict[str, str]
CollisionKeyFnT: TypeAlias = Callable[[RowT], str]
CollisionSignatureFnT: TypeAlias = Callable[[RowT], str]

DEFAULT_APPROVED_ALIAS_PATH = Path("data/course_aliases/approved_course_aliases.tsv")


def load_approved_course_aliases(
    path: Path = DEFAULT_APPROVED_ALIAS_PATH,
) -> tuple[CourseAliasMapT, RowsT]:
    """Load approved source->target course aliases from a TSV/CSV file."""
    alias_map: CourseAliasMapT = {}
    report_rows: RowsT = []
    for row in read_rows(path):
        source_key = course_key(
            row.get("source_course_dept"), row.get("source_course_no")
        )
        target_key = course_key(
            row.get("target_course_dept"), row.get("target_course_no")
        )
        action = "loaded" if source_key and target_key else "skipped_unkeyed"
        if source_key and target_key and source_key != target_key:
            alias_map[source_key] = target_key
        elif source_key == target_key:
            action = "skipped_noop"
        report_rows.append(
            {
                "source_course_key": source_key,
                "target_course_key": target_key,
                "source_course_dept": row.get("source_course_dept", ""),
                "source_course_no": row.get("source_course_no", ""),
                "target_course_dept": row.get("target_course_dept", ""),
                "target_course_no": row.get("target_course_no", ""),
                "reason": row.get("reason", ""),
                "action": action,
            }
        )
    return alias_map, report_rows


def apply_course_aliases(rows: Iterable[RowT], alias_map: CourseAliasMapT) -> RowsT:
    """Return copied rows with approved course identities rewritten."""
    if not alias_map:
        return [row.copy() for row in rows]
    aliased_rows: RowsT = []
    for row in rows:
        aliased_rows.append(_aliased_row(row, alias_map))
    return aliased_rows


def collapse_aliased_duplicates(
    rows: Iterable[RowT],
    *,
    domain: str,
    key_fn: CollisionKeyFnT,
    signature_fn: CollisionSignatureFnT,
) -> tuple[RowsT, RowsT]:
    """Collapse post-alias duplicate operational rows and report collisions."""
    kept_rows: RowsT = []
    seen_rows: dict[str, RowT] = {}
    seen_signatures: dict[str, str] = {}
    collisions: RowsT = []
    for row in rows:
        key = key_fn(row)
        if not key:
            kept_rows.append(row)
            continue
        signature = signature_fn(row)
        kept_row = seen_rows.get(key)
        if kept_row is None:
            seen_rows[key] = row
            seen_signatures[key] = signature
            kept_rows.append(row)
            continue
        action = (
            "collapsed_duplicate"
            if seen_signatures.get(key) == signature
            else "kept_first_conflict_for_review"
        )
        collisions.append(_collision_row(domain, key, kept_row, row, action))
    return kept_rows, collisions


def grade_collision_key(row: RowT) -> str:
    """Return the import identity for one grade row after aliasing."""
    return _join_key(
        row.get("student_id", ""),
        normalize_academic_year(row.get("academic_year", "")),
        row.get("semester_no", ""),
        course_key(row.get("course_dept"), row.get("course_no")),
        row.get("section_no", "") or "1",
    )


def grade_collision_signature(row: RowT) -> str:
    """Return comparable grade content for duplicate detection."""
    return _join_key(
        row.get("grade_code", ""),
        row.get("credit_hours", ""),
        row.get("curriculum", ""),
        row.get("college_code", ""),
    )


def registration_collision_key(row: RowT) -> str:
    """Return the import identity for one registration row after aliasing."""
    return _join_key(
        row.get("student_id", ""),
        normalize_academic_year(row.get("academic_year", "")),
        row.get("semester_no", ""),
        course_key(row.get("course_dept"), row.get("course_no")),
        row.get("section_no", "") or "1",
    )


def registration_collision_signature(row: RowT) -> str:
    """Return comparable registration content for duplicate detection."""
    return _join_key(
        row.get("status", ""),
        row.get("credit_hours", ""),
        row.get("curriculum", ""),
        row.get("college_code", ""),
    )


def _aliased_row(row: RowT, alias_map: CourseAliasMapT) -> RowT:
    """Return one copied row with course_dept/course_no rewritten when approved."""
    source_key = course_key(row.get("course_dept"), row.get("course_no"))
    target_key = alias_map.get(source_key)
    if not target_key:
        return row.copy()
    target_dept, target_no = split_course_code(target_key)
    aliased = row.copy()
    if target_dept and target_no:
        aliased["course_dept"] = target_dept
        aliased["course_no"] = target_no
    return aliased


def _collision_row(
    domain: str,
    key: str,
    kept_row: RowT,
    duplicate_row: RowT,
    action: str,
) -> RowT:
    """Return one duplicate/collision audit row."""
    return {
        "domain": domain,
        "record_key": key,
        "action": action,
        "kept_course_key": course_key(
            kept_row.get("course_dept"), kept_row.get("course_no")
        ),
        "duplicate_course_key": course_key(
            duplicate_row.get("course_dept"), duplicate_row.get("course_no")
        ),
        "student_id": duplicate_row.get("student_id", ""),
        "academic_year": duplicate_row.get("academic_year", ""),
        "semester_no": duplicate_row.get("semester_no", ""),
        "kept_source_name": kept_row.get("source_name", ""),
        "duplicate_source_name": duplicate_row.get("source_name", ""),
    }


def _join_key(*parts: str) -> str:
    """Join key parts only when all required parts are present."""
    cleaned = [str(part or "").strip() for part in parts]
    if not all(cleaned):
        return ""
    return "|".join(cleaned)


__all__ = [
    "DEFAULT_APPROVED_ALIAS_PATH",
    "CourseAliasMapT",
    "apply_course_aliases",
    "collapse_aliased_duplicates",
    "grade_collision_key",
    "grade_collision_signature",
    "load_approved_course_aliases",
    "registration_collision_key",
    "registration_collision_signature",
]
