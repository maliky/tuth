"""Conflict report builders for source-truth outputs."""

from __future__ import annotations

from typing import TypeAlias

from app.shared.source_truth.io import RowT

RowsT: TypeAlias = list[RowT]


def build_conflicts(
    smartschool_integrity: RowsT,
    historical_courses: RowsT,
    course_aliases: RowsT,
    invalid_course_identities: RowsT,
) -> RowsT:
    """Build the high-priority manual review list."""
    rows: RowsT = []
    for row in smartschool_integrity:
        if row.get("selected_source") == "fallback_required":
            rows.append(
                {
                    "domain": "smartschool_export",
                    "key": row.get("table_name", ""),
                    "issue": row.get("status", ""),
                    "recommended_action": "regenerate_latest_csv_or_use_fallback",
                }
            )
    matched_keys = {row.get("source_course_key", "") for row in course_aliases}
    for row in historical_courses:
        key = row.get("course_key", "")
        if key and key not in matched_keys:
            rows.append(
                {
                    "domain": "course",
                    "key": key,
                    "issue": "no_tucurricula_candidate",
                    "recommended_action": "review_as_historical_only_or_alias",
                }
            )
    for row in invalid_course_identities:
        rows.append(
            {
                "domain": "course_identity",
                "key": f"{row.get('table_name', '')}:{row.get('row_number', '')}",
                "issue": row.get("reason", ""),
                "recommended_action": "repair_source_or_confirm_historical_skip",
            }
        )
    return rows
