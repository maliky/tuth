"""Report specifications and summary writing for source-truth builds."""

from __future__ import annotations

from typing import TypeAlias

from app.shared.source_truth.io import HeadersT, RowT

RowsT: TypeAlias = list[RowT]
CountsT: TypeAlias = dict[str, int]
ReportSpecT: TypeAlias = tuple[str, HeadersT, RowsT]


def report_specs(**rows_by_name: RowsT) -> tuple[ReportSpecT, ...]:
    """Return report filenames, headers, and rows."""
    return (
        (
            "source_inventory.tsv",
            (
                "source_name",
                "path",
                "actual_rows",
                "column_count",
                "size_bytes",
                "sha256",
                "headers",
                "status",
            ),
            rows_by_name["inventory"],
        ),
        (
            "table_integrity.tsv",
            (
                "table_name",
                "manifest_rows",
                "actual_rows",
                "column_count",
                "status",
                "selected_source",
                "selected_path",
            ),
            rows_by_name["smartschool_integrity"],
        ),
        ("grapro_mdb_tables.tsv", ("table_name", "status"), rows_by_name["mdb_tables"]),
        (
            "course_witnesses.tsv",
            (
                "source_name",
                "course_key",
                "course_dept",
                "course_no",
                "course_title",
                "credit_hours",
                "college_code",
                "source_path",
            ),
            rows_by_name["course_witnesses"],
        ),
        (
            "course_alias_candidates.tsv",
            (
                "source_course_key",
                "source_label",
                "source_name",
                "target_course_key",
                "target_label",
                "target_name",
                "score",
                "recommendation",
            ),
            rows_by_name["course_aliases"],
        ),
        (
            "approved_course_aliases.tsv",
            (
                "source_course_key",
                "target_course_key",
                "source_course_dept",
                "source_course_no",
                "target_course_dept",
                "target_course_no",
                "reason",
                "action",
            ),
            rows_by_name["approved_course_aliases"],
        ),
        (
            "course_alias_collisions.tsv",
            (
                "domain",
                "record_key",
                "action",
                "kept_course_key",
                "duplicate_course_key",
                "student_id",
                "academic_year",
                "semester_no",
                "kept_source_name",
                "duplicate_source_name",
            ),
            rows_by_name["course_alias_collisions"],
        ),
        (
            "invalid_course_identity_rows.tsv",
            (
                "source_name",
                "source_path",
                "table_name",
                "row_number",
                "raw_course_dept",
                "raw_course_no",
                "normalized_dept_attempt",
                "normalized_no_attempt",
                "reason",
            ),
            rows_by_name["invalid_course_identities"],
        ),
        (
            "course_identity_repairs.tsv",
            (
                "source_name",
                "source_path",
                "table_name",
                "row_number",
                "raw_course_dept",
                "raw_course_no",
                "course_dept",
                "course_no",
                "parse_source",
                "repair_reason",
            ),
            rows_by_name["repaired_course_identities"],
        ),
        (
            "curriculum_mapping_candidates.tsv",
            (
                "source_curriculum",
                "source_long_name",
                "candidate_rank",
                "target_curriculum",
                "target_long_name",
                "score",
                "recommendation",
            ),
            rows_by_name["curriculum_aliases"],
        ),
        (
            "student_identity_matches.tsv",
            (
                "source_student_id",
                "source_student_name",
                "source_name",
                "target_student_id",
                "target_student_name",
                "target_name",
                "score",
                "recommendation",
            ),
            rows_by_name["student_matches"],
        ),
        (
            "student_curriculum_matches.tsv",
            (
                "student_id",
                "student_name",
                "source_curriculum",
                "standardized_curriculum",
                "target_curriculum",
                "match_method",
                "score",
            ),
            rows_by_name["student_curriculum_matches"],
        ),
        (
            "grapro_student_supplements.tsv",
            (
                "action",
                "student_id",
                "student_name",
                "legacy_curriculum",
                "source_name",
                "source_path",
            ),
            rows_by_name["grapro_student_supplements"],
        ),
        (
            "grapro_grade_supplements.tsv",
            (
                "action",
                "grade_key",
                "student_id",
                "academic_year",
                "semester_no",
                "course_dept",
                "course_no",
                "section_no",
                "grade_code",
                "source_name",
                "source_path",
                "source_row_number",
            ),
            rows_by_name["grapro_grade_supplements"],
        ),
        (
            "grapro_grade_skipped.tsv",
            (
                "source_name",
                "source_path",
                "row_number",
                "student_id",
                "term_id",
                "item_id",
                "grade_code",
                "reason",
            ),
            rows_by_name["grapro_grade_skipped"],
        ),
        (
            "canonical_courses.tsv",
            (
                "course_dept",
                "course_no",
                "college_code",
                "course_title",
                "credit_hours",
                "description",
                "canonical_status",
                "source_name",
                "source_path",
            ),
            rows_by_name["canonical_courses"],
        ),
        (
            "canonical_curricula.tsv",
            (
                "curriculum",
                "long_name",
                "college_code",
                "status",
                "is_active",
                "canonical_status",
                "source_name",
                "source_path",
            ),
            rows_by_name["canonical_curricula"],
        ),
        (
            "canonical_curriculum_courses.tsv",
            (
                "curriculum",
                "course_dept",
                "course_no",
                "credit_hours",
                "year_number",
                "semester_number",
                "level_number",
                "required_group_number",
                "min_validated_credits",
                "canonical_status",
                "source_name",
                "source_path",
            ),
            rows_by_name["canonical_curri_courses"],
        ),
        (
            "conflicts_for_review.tsv",
            ("domain", "key", "issue", "recommended_action"),
            rows_by_name["conflicts"],
        ),
    )


def summary_text(
    output_dir: object, counts: CountsT, smartschool_integrity: RowsT
) -> str:
    """Return a compact summary for the run."""
    fallback_count = sum(
        1
        for row in smartschool_integrity
        if row.get("selected_source") == "fallback_required"
    )
    lines = [
        "TUSIS source-truth build",
        f"output_dir: {output_dir}",
        "mutation: none",
        f"smartschool_tables_requiring_fallback: {fallback_count}",
        "",
        "counts:",
    ]
    lines.extend(f"  {name}: {count}" for name, count in sorted(counts.items()))
    lines.extend(
        [
            "",
            "next_review:",
            "  1. Review table_integrity.tsv for broken latest SmartSchool exports.",
            "  2. Review course_identity_repairs.tsv for normalized legacy course rows.",
            "  3. Review invalid_course_identity_rows.tsv for skipped course rows.",
            "  4. Review course_alias_candidates.tsv before accepting aliases.",
            "  5. Review approved_course_aliases.tsv and course_alias_collisions.tsv.",
            "  6. Review student_identity_matches.tsv before merging identities.",
            "  7. Dry-run import_ready TSV files before applying to Django.",
        ]
    )
    return "\n".join(lines) + "\n"
