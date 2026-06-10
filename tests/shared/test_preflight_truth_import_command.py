"""Tests for import-ready truth preflight validation."""

from __future__ import annotations

from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError


def _write(path: Path, text: str) -> None:
    """Write a small truth fixture file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_preflight_rejects_duplicate_student_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Duplicate student ids should fail before a destructive rebuild starts."""
    monkeypatch.chdir(tmp_path)
    truth_dir = tmp_path / "truth"
    _write(truth_dir / "academic_curriculum.tsv", "curriculum\n")
    _write(truth_dir / "academic_course.tsv", "course_dept\tcourse_no\n")
    _write(
        truth_dir / "academic_curriculum_course.tsv",
        "curriculum\tcourse_dept\tcourse_no\n",
    )
    _write(truth_dir / "academic_curriculum_requirement.tsv", "curriculum\n")
    _write(
        truth_dir / "people_full_student.tsv",
        "student_id\tusername\tbirth_date\n100\tada.one\t2000-01-01\n100\tada.two\t\n",
    )
    _write(
        truth_dir / "registry_registration.tsv",
        "student_id\tacademic_year\tsemester_no\tcourse_dept\tcourse_no\n",
    )
    _write(
        truth_dir / "full_grades.tsv",
        "student_id\tacademic_year\tsemester_no\tcourse_dept\tcourse_no\tgrade_code\n",
    )
    _write(
        truth_dir / "finance_payments.tsv",
        "student_id\tacademic_year\tsemester_no\tamount_paid\n",
    )

    with pytest.raises(CommandError, match="Truth preflight failed"):
        call_command("preflight_truth_import", truth_dir=str(truth_dir))
