"""Tests for course-level finance billing policy."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from app.academics.models.department import Department
from app.finance.course_fee_policy import (
    course_fee_breakdown,
    tuition_rate_for_semester,
    unresolved_lab_fee_candidate_rows,
)
from app.registry.models.credit_hours import CreditHour

pytestmark = pytest.mark.django_db


def _configure_course(curriculum_course, dept: str, number: str, credits: int) -> None:
    """Set a test curriculum-course identity and credit value."""
    course = curriculum_course.course
    course.department = Department.get_dft(dept)
    course.number = number
    course.code = ""
    course.short_code = ""
    course.save()
    curriculum_course.credit_hours = CreditHour.objects.get(code=credits)
    curriculum_course.save(update_fields=["credit_hours"])


def test_course_fee_policy_enforces_minimum_for_low_credit_courses(
    curriculum_course_factory,
    sem_factory,
) -> None:
    """Courses with fewer than three credits should still bill at least 15 USD."""
    curriculum_course = curriculum_course_factory("901", "CURR_FEE_MIN")
    semester = sem_factory(3, datetime(2026, 6, 1))
    _configure_course(curriculum_course, "EEDU", "301", 0)

    breakdown = course_fee_breakdown(curriculum_course, semester)

    assert breakdown["base_amount"] == Decimal("15.00")
    assert breakdown["total_amount"] == Decimal("15.00")


def test_course_fee_policy_sets_general_science_four_credit_courses_to_15(
    curriculum_course_factory,
    sem_factory,
) -> None:
    """General CHEM/BIO/PHYS 101/102/201/202 courses are flat 15 USD."""
    curriculum_course = curriculum_course_factory("101", "CURR_FEE_SCI")
    semester = sem_factory(3, datetime(2026, 6, 1))
    _configure_course(curriculum_course, "CHEM", "101", 4)

    breakdown = course_fee_breakdown(curriculum_course, semester)

    assert breakdown["base_amount"] == Decimal("15.00")
    assert breakdown["reason"] == "course_base_override"


def test_course_fee_policy_keeps_non_general_four_credit_course_at_rate_floor(
    curriculum_course_factory,
    sem_factory,
) -> None:
    """Unknown 4-credit lab courses keep rate billing until an extra fee is explicit."""
    curriculum_course = curriculum_course_factory("302", "CURR_FEE_LAB")
    semester = sem_factory(3, datetime(2026, 6, 1))
    _configure_course(curriculum_course, "BIOL", "302", 4)

    breakdown = course_fee_breakdown(curriculum_course, semester)

    assert breakdown["base_amount"] == Decimal("20.00")
    assert breakdown["extra_amount"] == Decimal("0.00")


def test_tuition_rate_for_current_vacation_semester_uses_smartschool_rate(
    sem_factory,
) -> None:
    """2025/2026 Sem3 uses the SmartSchool 5 USD per-credit rate."""
    semester = sem_factory(3, datetime(2026, 6, 1))

    assert tuition_rate_for_semester(semester) == Decimal("5.00")


def test_tuition_rate_for_2023_semester_two_uses_corrected_smartschool_rate(
    sem_factory,
) -> None:
    """2023/2024 Sem2 imports the corrected 5 USD per-credit rate."""
    semester = sem_factory(2, datetime(2023, 8, 1))

    assert tuition_rate_for_semester(semester) == Decimal("5.00")


def test_unresolved_lab_fee_candidate_report_flags_non_general_four_credit_courses(
    regio_factory,
) -> None:
    """The lab-fee report should list non-general 4-credit registrations."""
    registration = regio_factory("fee_policy_lab_student", "CURR_FEE_REPORT", "302", 3)
    _configure_course(registration.section.curriculum_course, "BIOL", "302", 4)

    rows = unresolved_lab_fee_candidate_rows([registration])

    assert rows[0]["course_key"] == "BIOL302"
    assert rows[0]["computed_amount"] == "20.00"
    assert rows[0]["registration_count"] == "1"


def test_unresolved_lab_fee_candidate_report_ignores_general_science_courses(
    regio_factory,
) -> None:
    """General science 4-credit courses should not be lab-extra candidates."""
    registration = regio_factory("fee_policy_sci_student", "CURR_FEE_REPORT2", "101", 3)
    _configure_course(registration.section.curriculum_course, "PHYS", "101", 4)

    assert unresolved_lab_fee_candidate_rows([registration]) == []
