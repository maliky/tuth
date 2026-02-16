"""Tests for registrar grades dashboard default semester selection."""

from __future__ import annotations

from typing import cast

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _selected_sem_value(response) -> str:
    """Return the selected semester value from dashboard context options."""
    selected_options = [
        option for option in response.context["semester_options"] if option["selected"]
    ]
    assert len(selected_options) == 1
    return cast(str, selected_options[0]["value"])


def test_dashboard_dfts_to_latest_sem_with_grades(
    client,
    reg_user_factory,
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
    reg_grade_factory,
) -> None:
    """Default semester should be the most recent semester that has grades."""
    user = reg_user_factory("registrar_dashboard_default")
    _academic_year, previous, current = reg_sem_pair_factory()

    previous_section, curriculum = reg_sec_factory(
        previous,
        course_number="301",
        curriculum_short_name="CURRI_REG_VIEW",
    )
    previous_student = reg_std_factory(
        "registrar_view_prev",
        curriculum,
        previous,
    )
    reg_grade_factory(previous_student, previous_section)

    current_section, _current_curriculum = reg_sec_factory(
        current,
        course_number="302",
        curriculum_short_name="CURRI_REG_VIEW",
    )
    current_student = reg_std_factory(
        "registrar_view_current",
        curriculum,
        current,
    )
    reg_grade_factory(current_student, current_section)

    client.force_login(user)
    response = client.get(reverse("reg_grades_dashboard"))

    assert response.status_code == 200
    assert _selected_sem_value(response) == str(current.id)


def test_dashboard_dfts_to_all_sems_without_grades(
    client,
    reg_user_factory,
    reg_sem_pair_factory,
) -> None:
    """Default semester should be 'All semesters' when no grades exist."""
    user = reg_user_factory("registrar_dashboard_no_grades")
    reg_sem_pair_factory()

    client.force_login(user)
    response = client.get(reverse("reg_grades_dashboard"))

    assert response.status_code == 200
    assert _selected_sem_value(response) == "all"
