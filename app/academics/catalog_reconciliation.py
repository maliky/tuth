"""Compare org-derived TUCurricula TSVs against current TUSIS catalog rows."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

from app.academics.catalog_reconciliation_actions import (
    course_action,
    curriculum_action,
    curriculum_course_action,
)
from app.academics.current_usage import (
    CurrentUsageT,
    iter_current_course_rows,
    iter_current_curriculum_course_rows,
    iter_current_curriculum_rows,
    load_current_usage,
)
from app.academics.curriculum_mapping_candidates import (
    build_curriculum_mapping_candidates,
)
from app.academics.reconciliation_io import (
    RowT,
    course_key,
    normalize_token,
    read_tsv,
    split_course_key,
    write_tsv,
)

RowIndexT: TypeAlias = dict[str, list[RowT]]
KeyFnT: TypeAlias = Callable[[RowT], str]


@dataclass(frozen=True)
class ReconciliationSummaryT:
    """Summary of generated reconciliation report files."""

    output_dir: Path
    counts: dict[str, int]


def _index_rows(rows: Iterable[RowT], key_fn: KeyFnT) -> RowIndexT:
    """Group rows by deterministic reconciliation key."""
    index: RowIndexT = {}
    for row in rows:
        key = key_fn(row)
        if not key:
            continue
        index.setdefault(key, []).append(row)
    return index


def _org_course_key(row: RowT) -> str:
    """Return the org-derived course key."""
    return split_course_key(row.get("source_course_key")) or course_key(
        row.get("course_dept"), row.get("course_no")
    )


def _curriculum_key(row: RowT) -> str:
    """Return normalized curriculum key."""
    return normalize_token(row.get("curriculum") or row.get("curriculum_key"))


def _curriculum_course_key(row: RowT) -> str:
    """Return normalized curriculum-course key."""
    return f"{_curriculum_key(row)}|{_org_course_key(row)}"


def _unique(rows: Iterable[RowT], field: str) -> str:
    """Return a compact semicolon-separated list of distinct field values."""
    values = sorted({row.get(field, "") for row in rows if row.get(field, "")})
    return "; ".join(values)


def _sum_usage(rows: Iterable[RowT]) -> int:
    """Return summed usage_total values from current rows."""
    return sum(int(row.get("usage_total") or 0) for row in rows)


def _ids(rows: Iterable[RowT], field: str) -> str:
    """Return comma-separated current object ids for review."""
    return ",".join(row.get(field, "") for row in rows if row.get(field, ""))


def build_course_reconciliation(usage: CurrentUsageT, import_dir: Path) -> list[RowT]:
    """Return current-vs-org course reconciliation rows."""
    current = _index_rows(iter_current_course_rows(usage), lambda row: row["course_key"])
    org = _index_rows(read_tsv(import_dir / "academic_course.tsv"), _org_course_key)
    rows: list[RowT] = []
    for key in sorted(set(current) | set(org)):
        current_rows = current.get(key, [])
        org_rows = org.get(key, [])
        category, action, notes = course_action(current_rows, org_rows)
        rows.append(
            {
                "course_key": key,
                "category": category,
                "action": action,
                "current_course_ids": _ids(current_rows, "course_id"),
                "org_row_count": str(len(org_rows)),
                "current_row_count": str(len(current_rows)),
                "usage_total": str(_sum_usage(current_rows)),
                "current_title": _unique(current_rows, "course_title"),
                "org_title": _unique(org_rows, "course_title"),
                "notes": notes,
            }
        )
    return rows


def build_curriculum_reconciliation(usage: CurrentUsageT, import_dir: Path) -> list[RowT]:
    """Return current-vs-org curriculum reconciliation rows."""
    current = _index_rows(iter_current_curriculum_rows(usage), _curriculum_key)
    org = _index_rows(read_tsv(import_dir / "academic_curriculum.tsv"), _curriculum_key)
    rows: list[RowT] = []
    for key in sorted(set(current) | set(org)):
        current_rows = current.get(key, [])
        org_rows = org.get(key, [])
        category, action, notes = curriculum_action(current_rows, org_rows)
        rows.append(
            {
                "curriculum_key": key,
                "category": category,
                "action": action,
                "current_curriculum_ids": _ids(current_rows, "curriculum_id"),
                "org_row_count": str(len(org_rows)),
                "current_row_count": str(len(current_rows)),
                "usage_total": str(_sum_usage(current_rows)),
                "current_long_name": _unique(current_rows, "long_name"),
                "org_long_name": _unique(org_rows, "long_name"),
                "notes": notes,
            }
        )
    return rows


def build_curriculum_course_reconciliation(
    usage: CurrentUsageT, import_dir: Path
) -> list[RowT]:
    """Return current-vs-org curriculum-course reconciliation rows."""
    current = _index_rows(
        iter_current_curriculum_course_rows(usage), _curriculum_course_key
    )
    org = _index_rows(
        read_tsv(import_dir / "academic_curriculum_course.tsv"), _curriculum_course_key
    )
    rows: list[RowT] = []
    for key in sorted(set(current) | set(org)):
        current_rows = current.get(key, [])
        org_rows = org.get(key, [])
        category, action, notes = curriculum_course_action(current_rows, org_rows)
        rows.append(
            {
                "curriculum_course_key": key,
                "category": category,
                "action": action,
                "current_curriculum_course_ids": _ids(
                    current_rows, "curriculum_course_id"
                ),
                "org_row_count": str(len(org_rows)),
                "current_row_count": str(len(current_rows)),
                "usage_total": str(_sum_usage(current_rows)),
                "current_credit_hours": _unique(current_rows, "credit_hours"),
                "org_credit_hours": _unique(org_rows, "credit_hours"),
                "notes": notes,
            }
        )
    return rows


def write_catalog_reconciliation(
    import_dir: Path, output_dir: Path, usage: CurrentUsageT | None = None
) -> ReconciliationSummaryT:
    """Write action-oriented org-vs-current catalog reconciliation TSV files."""
    usage = usage or load_current_usage()
    specs = (
        (
            "course_reconciliation.tsv",
            (
                "course_key",
                "category",
                "action",
                "current_course_ids",
                "org_row_count",
                "current_row_count",
                "usage_total",
                "current_title",
                "org_title",
                "notes",
            ),
            build_course_reconciliation(usage, import_dir),
        ),
        (
            "curriculum_reconciliation.tsv",
            (
                "curriculum_key",
                "category",
                "action",
                "current_curriculum_ids",
                "org_row_count",
                "current_row_count",
                "usage_total",
                "current_long_name",
                "org_long_name",
                "notes",
            ),
            build_curriculum_reconciliation(usage, import_dir),
        ),
        (
            "curriculum_mapping_candidates.tsv",
            (
                "current_curriculum_id",
                "current_curriculum",
                "current_long_name",
                "usage_total",
                "candidate_rank",
                "org_curriculum",
                "org_long_name",
                "similarity",
                "recommendation",
            ),
            build_curriculum_mapping_candidates(usage, import_dir),
        ),
        (
            "curriculum_course_reconciliation.tsv",
            (
                "curriculum_course_key",
                "category",
                "action",
                "current_curriculum_course_ids",
                "org_row_count",
                "current_row_count",
                "usage_total",
                "current_credit_hours",
                "org_credit_hours",
                "notes",
            ),
            build_curriculum_course_reconciliation(usage, import_dir),
        ),
    )
    counts: dict[str, int] = {}
    for filename, headers, rows in specs:
        counts[filename] = write_tsv(output_dir / filename, headers, rows)
    return ReconciliationSummaryT(output_dir=output_dir, counts=counts)
