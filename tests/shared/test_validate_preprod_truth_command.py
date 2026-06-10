"""Tests for import-ready truth database validation helpers."""

from __future__ import annotations

from pathlib import Path

from app.shared.management.commands.validate_preprod_truth import _expected_counts


def test_expected_counts_deduplicate_requirement_members(tmp_path: Path) -> None:
    """Requirement expectations should match import-resource identity."""
    truth_dir = tmp_path / "truth"
    truth_dir.mkdir()
    (truth_dir / "academic_curriculum_requirement.tsv").write_text(
        "\t".join(
            [
                "college_code",
                "curriculum_college_code",
                "course_college_code",
                "curriculum",
                "course_dept",
                "course_no",
                "required_course_college_code",
                "required_course_dept",
                "required_course_no",
                "requirement_kind",
                "requirement_label",
            ]
        )
        + "\n"
        + "\t".join(
            [
                "COAS",
                "COAS",
                "COAS",
                "CAS-BIOL",
                "PHYS",
                "101",
                "COAS",
                "MATH",
                "102",
                "prereq_all",
                "source prereq_all PHYS101",
            ]
        )
        + "\n"
        + "\t".join(
            [
                "COAS",
                "COAS",
                "COAS",
                "CAS-BIOL",
                "PHYS",
                "101",
                "COAS",
                "MATH",
                "102",
                "prereq_all",
                "source prereq_all PHYS101",
            ]
        )
        + "\n"
        + "\t".join(
            [
                "COAS",
                "COAS",
                "COAS",
                "CAS-BIOL",
                "PHYS",
                "101",
                "COAS",
                "MATH",
                "103",
                "prereq_all",
                "source prereq_all PHYS101",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert _expected_counts(truth_dir)["requirement_members"] == 2
