"""Tests for canonical college-code data normalization."""

from __future__ import annotations

import pytest

from app.academics.college_normalization import normalize_college_records
from app.academics.models import College, Course, CurriStatus, Curriculum, Department


@pytest.mark.django_db
def test_normalize_college_records_merges_legacy_codes() -> None:
    """Legacy college rows should become canonical rows with relations preserved."""
    arts = College.objects.create(code="COAS", long_name="College of Arts and Sciences")
    education = College.objects.create(code="COED", long_name="College of Education")
    Department.objects.create(code="MATH", college=arts)
    education_department = Department.objects.create(code="EDU", college=education)
    Course.objects.create(department=education_department, number="101")
    CurriStatus._populate_attributes_and_db()
    Curriculum.objects.create(
        short_name="CED-PEDU",
        college=education,
        long_name="Primary Education",
        status_id="pending",
    )

    result = normalize_college_records()

    assert result.renamed >= 2
    assert College.objects.filter(code__in=["COAS", "COED", "CED"]).count() == 0
    assert Department.objects.get(code="MATH").college.code == "CAS"
    education_department = Department.objects.get(code="EDU")
    assert education_department.college.code == "EDRCE"
    assert education_department.shortname == "EDRCE_EDU"
    assert Course.objects.get(number="101").code == "EDRCE_EDU101"
    assert (
        Curriculum.objects.get(long_name="Primary Education").short_name == "EDRCE-PEDU"
    )
