"""Tests for approved course aliases in source-truth outputs."""

from __future__ import annotations

from pathlib import Path

from app.shared.source_truth.course_aliases import (
    apply_course_aliases,
    collapse_aliased_duplicates,
    grade_collision_key,
    grade_collision_signature,
    load_approved_course_aliases,
)
from app.shared.source_truth.fuzzy import build_course_alias_candidates


def test_approved_course_aliases_rewrite_copied_rows(tmp_path: Path) -> None:
    """Approved aliases mutate import rows without mutating raw witnesses."""
    alias_path = tmp_path / "aliases.tsv"
    alias_path.write_text(
        "source_course_dept\tsource_course_no\ttarget_course_dept\ttarget_course_no\t"
        "reason\n"
        "HIST\t102\tHIST\t202\tWorld History duplicate\n",
        encoding="utf-8",
    )
    alias_map, report_rows = load_approved_course_aliases(alias_path)
    raw_rows = [{"course_dept": "HIST", "course_no": "102", "grade_code": "B"}]

    aliased_rows = apply_course_aliases(raw_rows, alias_map)

    assert report_rows[0]["action"] == "loaded"
    assert raw_rows[0]["course_no"] == "102"
    assert aliased_rows[0]["course_no"] == "202"


def test_course_alias_collision_report_collapses_duplicate_grades() -> None:
    """Alias-induced duplicate grade rows should collapse with an audit row."""
    rows = [
        {
            "source_name": "latest_smartschool",
            "student_id": "31625",
            "academic_year": "2024/2025",
            "semester_no": "1",
            "course_dept": "HIST",
            "course_no": "202",
            "section_no": "1",
            "grade_code": "B",
            "credit_hours": "3",
        },
        {
            "source_name": "grapro_legacy",
            "student_id": "31625",
            "academic_year": "2024/2025",
            "semester_no": "1",
            "course_dept": "HIST",
            "course_no": "202",
            "section_no": "1",
            "grade_code": "B",
            "credit_hours": "3",
        },
    ]

    kept_rows, collisions = collapse_aliased_duplicates(
        rows,
        domain="grade",
        key_fn=grade_collision_key,
        signature_fn=grade_collision_signature,
    )

    assert len(kept_rows) == 1
    assert collisions[0]["action"] == "collapsed_duplicate"
    assert collisions[0]["record_key"].endswith("HIST202|1")


def test_course_alias_candidates_promote_close_code_title_duplicates() -> None:
    """Fuzzy candidates should flag close course-code/title duplicates."""
    candidates = build_course_alias_candidates(
        [
            {
                "course_dept": "HIST",
                "course_no": "102",
                "course_title": "World History",
                "source_name": "smartschool",
            }
        ],
        [
            {
                "course_dept": "HIST",
                "course_no": "202",
                "course_title": "World History",
                "source_name": "tucurricula",
            }
        ],
    )

    assert candidates[0]["target_course_key"] == "HIST202"
    assert candidates[0]["recommendation"] == "strong_title_and_close_code_match"
