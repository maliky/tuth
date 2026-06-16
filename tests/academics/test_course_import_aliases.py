"""Regression tests for course import row aliases."""

from __future__ import annotations

import pytest
from tablib import Dataset

from app.academics.admin.course_resource import CrsResource
from app.academics.admin.resources import CurriCrsResource
from app.academics.admin.widgets import CrsWgt
from app.academics.models.curriculum_course import CurriCrs


@pytest.mark.django_db
def test_crs_widget_accepts_course_dept_alias() -> None:
    """CrsWgt should use course_dept when dept_code is absent."""
    course = CrsWgt().clean(
        None,
        row={
            "course_dept": "ACCT",
            "course_no": "101",
            "college_code": "CBA",
            "course_title": "Accounting I",
        },
    )

    assert course.department.code == "ACCT"
    assert course.number == "101"
    assert course.title == "Accounting I"


@pytest.mark.django_db
def test_crs_widget_normalizes_dirty_smartschool_course_identity() -> None:
    """Dirty SmartSchool course identity cells should resolve to one course."""
    course = CrsWgt().clean(
        None,
        row={
            "course_dept": "Math 003",
            "course_no": "Math 003",
            "college_code": "COAS",
            "course_title": "Remedial Math",
        },
    )

    assert course.department.code == "MATH"
    assert course.department.college.code == "CAS"
    assert course.number == "003"
    assert course.title == "Remedial Math"


def test_course_resource_skips_unparseable_course_identity() -> None:
    """Command-line Course imports can skip unparseable legacy identities."""
    resource = CrsResource()
    row = {"course_dept": "ME", "course_no": "ME", "course_title": "Bad row"}

    assert resource.should_skip_row(row, 1) is True


def test_course_resource_normalizes_dirty_course_identity() -> None:
    """Course resource mutates recoverable rows before import-export lookup."""
    resource = CrsResource()
    row = {"course_dept": "Math 003", "course_no": "Math 003"}

    assert resource.should_skip_row(row, 1) is False
    assert row["course_dept"] == "MATH"
    assert row["course_no"] == "003"


def test_course_resource_pads_legacy_short_course_number() -> None:
    """Legacy one- or two-digit SmartSchool numbers are padded for import."""
    resource = CrsResource()
    row = {"course_dept": "MATH", "course_no": "3"}

    assert resource.should_skip_row(row, 1) is False
    assert row["course_dept"] == "MATH"
    assert row["course_no"] == "003"


@pytest.mark.django_db
def test_curricrs_resource_accepts_course_dept_rows() -> None:
    """CurriCrsResource should bind course_dept rows through CrsWgt."""
    dataset = Dataset(
        headers=[
            "curriculum",
            "course_dept",
            "course_no",
            "college_code",
            "course_title",
            "credit_hours",
        ]
    )
    dataset.append(["BACC", "ACCT", "101", "CBA", "Accounting I", "4"])

    result = CurriCrsResource().import_data(dataset, dry_run=False, raise_errors=True)

    assert not result.has_errors()
    curriculum_course = CurriCrs.objects.select_related(
        "course__department", "curriculum", "credit_hours"
    ).get()
    assert curriculum_course.curriculum.short_name == "BACC"
    assert curriculum_course.course.department.code == "ACCT"
    assert curriculum_course.course.number == "101"
    assert curriculum_course.credit_hours_id == 4


@pytest.mark.django_db
def test_curricrs_resource_defaults_credit_hours_when_missing() -> None:
    """Existing curriculum-course CSVs can omit credit_hours."""
    dataset = Dataset(
        headers=[
            "curriculum",
            "course_dept",
            "course_no",
            "college_code",
            "course_title",
        ]
    )
    dataset.append(["BACC", "ACCT", "102", "CBA", "Accounting II"])

    result = CurriCrsResource().import_data(dataset, dry_run=False, raise_errors=True)

    assert not result.has_errors()
    curriculum_course = CurriCrs.objects.select_related("credit_hours").get()
    assert curriculum_course.credit_hours_id == 3
