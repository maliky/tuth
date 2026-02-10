"""Tests for registrar grades dashboard default semester selection."""

from __future__ import annotations

from typing import cast

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _selected_semester_value(response) -> str:
    """Return the selected semester value from dashboard context options."""
    selected_options = [
        option for option in response.context["semester_options"] if option["selected"]
    ]
    assert len(selected_options) == 1
    return cast(str, selected_options[0]["value"])


def test_dashboard_defaults_to_latest_semester_with_grades(
    client,
    registrar_user_factory,
    registrar_semester_pair_factory,
    registrar_section_factory,
    registrar_student_factory,
    registrar_grade_factory,
) -> None:
    """Default semester should be the most recent semester that has grades."""
    user = registrar_user_factory("registrar_dashboard_default")
    _academic_year, previous, current = registrar_semester_pair_factory()

    previous_section, curriculum = registrar_section_factory(
        previous,
        course_number="301",
        curriculum_short_name="CURRI_REG_VIEW",
    )
    previous_student = registrar_student_factory(
        "registrar_view_prev",
        curriculum,
        previous,
    )
    registrar_grade_factory(previous_student, previous_section)

    current_section, _current_curriculum = registrar_section_factory(
        current,
        course_number="302",
        curriculum_short_name="CURRI_REG_VIEW",
    )
    current_student = registrar_student_factory(
        "registrar_view_current",
        curriculum,
        current,
    )
    registrar_grade_factory(current_student, current_section)

    client.force_login(user)
    response = client.get(reverse("registrar_grades_dashboard"))

    assert response.status_code == 200
    assert _selected_semester_value(response) == str(current.id)


def test_dashboard_defaults_to_all_semesters_without_grades(
    client,
    registrar_user_factory,
    registrar_semester_pair_factory,
) -> None:
    """Default semester should be 'All semesters' when no grades exist."""
    user = registrar_user_factory("registrar_dashboard_no_grades")
    registrar_semester_pair_factory()

    client.force_login(user)
    response = client.get(reverse("registrar_grades_dashboard"))

    assert response.status_code == 200
    assert _selected_semester_value(response) == "all"
