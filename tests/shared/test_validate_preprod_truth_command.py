"""Tests for import-ready truth database validation helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.registry.models.grade import Grade, GradeValue
from app.shared.management.commands.validate_preprod_truth import (
    _check_registered_vs_passing_credits,
    _expected_counts,
)


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
                "CAS",
                "CAS",
                "CAS",
                "CAS-BIOL",
                "PHYS",
                "101",
                "CAS",
                "MATH",
                "102",
                "prereq_all",
                "source prereq_all PHYS101",
            ]
        )
        + "\n"
        + "\t".join(
            [
                "CAS",
                "CAS",
                "CAS",
                "CAS-BIOL",
                "PHYS",
                "101",
                "CAS",
                "MATH",
                "102",
                "prereq_all",
                "source prereq_all PHYS101",
            ]
        )
        + "\n"
        + "\t".join(
            [
                "CAS",
                "CAS",
                "CAS",
                "CAS-BIOL",
                "PHYS",
                "101",
                "CAS",
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


@pytest.mark.django_db
def test_validate_truth_flags_registered_credit_gap(std_factory, sec_factory) -> None:
    """Validation should fail when passing grades exceed registration credits."""
    GradeValue._populate_attributes_and_db()
    student = std_factory("validate_credit_gap", "CURRI_VALIDATE_GAP")
    section = sec_factory("901", "CURRI_VALIDATE_GAP", 1, 1)
    Grade.objects.create(
        student=student,
        section=section,
        value=GradeValue.objects.get(code="b"),
    )
    failures: list[str] = []

    _check_registered_vs_passing_credits(failures)

    assert failures
    assert "registered credits below passing-grade credits" in failures[0]
