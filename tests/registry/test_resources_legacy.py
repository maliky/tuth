"""Tests for helpers in app.registry.admin.resources_legacy."""

from pathlib import Path

import pytest

from app.registry.admin.resources_legacy import normalize_semester, normalize_year
from app.shared.data import legacy_registration_rows


def test_normalize_year_formats():
    assert normalize_year("2019/2020") == "19-20"
    assert normalize_year("2019-2020") == "19-20"
    assert normalize_year("2019") == "19-20"
    assert normalize_year("19-20") == "19-20"
    assert normalize_year("") == ""


def test_normalize_semester_tokens():
    assert normalize_semester("First") == "1"
    assert normalize_semester("vac") == "3"
    assert normalize_semester(None) == "1"


@pytest.mark.django_db
def test_legacy_registration_rows_reads_override(tmp_path: Path):
    cache_clear = getattr(legacy_registration_rows, "cache_clear")
    cache_clear()
    csv_path = tmp_path / "legacy.csv"
    csv_path.write_text(
        "student_id,AcademicYear,Semester,Major,College\n"
        "123,2020/2021,First,CS,COET\n",
        encoding="utf-8",
    )
    rows = legacy_registration_rows(csv_path)
    assert rows == (
        {
            "student_id": "123",
            "AcademicYear": "2020/2021",
            "Semester": "First",
            "Major": "CS",
            "College": "COET",
        },
    )
    cache_clear()
