"""Tests for grouped curriculum-course requirement imports."""

from __future__ import annotations

import pytest
from tablib import Dataset

from app.academics.admin.requirement_resources import CurriCrsRequirementResource
from app.academics.models.prerequisite import Prerequisite
from app.academics.models.requirement_group import (
    CurriCrsReqGp,
    CurriCrsReqMember,
    ReqKind,
)

pytestmark = pytest.mark.django_db


def _dataset() -> Dataset:
    """Return a small grouped-requirement import dataset."""
    dataset = Dataset(
        headers=[
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
            "requirement_order",
            "member_order",
        ]
    )
    dataset.append(
        [
            "CAS",
            "CAS",
            "CAS",
            "CAS-PHYS",
            "PHYS",
            "102",
            "CAS",
            "MATH",
            "101",
            "prereq_all",
            "source prereq_all PHYS102",
            "1",
            "1",
        ]
    )
    dataset.append(
        [
            "CAS",
            "CAS",
            "CAS",
            "CAS-PHYS",
            "PHYS",
            "102",
            "CAS",
            "PHYS",
            "101",
            "coreq_all",
            "source coreq_all PHYS102",
            "3",
            "1",
        ]
    )
    return dataset


def test_curri_crs_requirement_resource_imports_grouped_rules() -> None:
    """Requirement resource should create grouped members idempotently."""
    resource = CurriCrsRequirementResource()
    result = resource.import_data(_dataset(), dry_run=False, raise_errors=True)

    assert not result.has_errors()
    assert CurriCrsReqGp.objects.count() == 2
    assert CurriCrsReqMember.objects.count() == 2
    assert CurriCrsReqGp.objects.filter(kind=ReqKind.PREREQ_ALL).exists()
    assert CurriCrsReqGp.objects.filter(kind=ReqKind.COREQ_ALL).exists()

    second_result = resource.import_data(_dataset(), dry_run=False, raise_errors=True)
    assert not second_result.has_errors()
    assert CurriCrsReqGp.objects.count() == 2
    assert CurriCrsReqMember.objects.count() == 2


def test_curri_crs_requirement_resource_mirrors_only_plain_prereqs() -> None:
    """Legacy Prerequisite rows should mirror prereq_all, not corequisites."""
    resource = CurriCrsRequirementResource()
    result = resource.import_data(_dataset(), dry_run=False, raise_errors=True)

    assert not result.has_errors()
    prerequisites = list(
        Prerequisite.objects.select_related("course", "prerequisite_course")
    )
    assert len(prerequisites) == 1
    assert prerequisites[0].course.short_code == "PHYS102"
    assert prerequisites[0].prerequisite_course.short_code == "MATH101"
