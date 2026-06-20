"""Tests for registrar grades dashboard default semester selection."""

from __future__ import annotations

from typing import cast

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _selected_sem_value(response) -> str:
    """Return the selected semester value from dashboard context options."""
    selected_options = [
        option for option in response.context["semester_options"] if option["selected"]
    ]
    assert len(selected_options) == 1
    return cast(str, selected_options[0]["value"])


def _perm(app_label: str, codename: str) -> Permission:
    """Return a concrete model permission scoped by app label."""
    return Permission.objects.get(
        content_type__app_label=app_label,
        codename=codename,
    )


def test_dashboard_dfts_to_all_sems_with_grades(
    client,
    reg_user_factory,
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
    reg_grade_factory,
) -> None:
    """Default semester should show all terms so transcript search is student-first."""
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
    assert _selected_sem_value(response) == "all"
    assert len(response.context["student_groups"]) == 2


def test_dashboard_explicit_semester_filter_limits_students(
    client,
    reg_user_factory,
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
    reg_grade_factory,
) -> None:
    """A selected semester should still scope the visible transcript list."""
    user = reg_user_factory("registrar_dashboard_semester")
    _academic_year, previous, current = reg_sem_pair_factory()
    previous_section, curriculum = reg_sec_factory(
        previous,
        course_number="303",
        curriculum_short_name="CURRI_REG_FILTER",
    )
    current_section, _current_curriculum = reg_sec_factory(
        current,
        course_number="304",
        curriculum_short_name="CURRI_REG_FILTER",
    )
    previous_student = reg_std_factory("registrar_filter_prev", curriculum, previous)
    current_student = reg_std_factory("registrar_filter_current", curriculum, current)
    reg_grade_factory(previous_student, previous_section)
    reg_grade_factory(current_student, current_section)

    client.force_login(user)
    response = client.get(reverse("reg_grades_dashboard"), {"semester": str(current.id)})
    student_groups = response.context["student_groups"]

    assert response.status_code == 200
    assert _selected_sem_value(response) == str(current.id)
    assert len(student_groups) == 1
    assert student_groups[0]["student"].id == current_student.id
    content = response.content.decode()
    assert "Download term transcripts" not in content
    assert "Select visible" in content
    assert "0 selected" in content
    assert "data-transcript-selected-count" in content
    assert "data-transcript-download-button" in content
    assert "data-transcript-checkbox" in content
    assert "data-transcript-layout-select" in content
    assert "Portrait - one grade column" in content
    assert "Landscape - two grade columns" in content
    assert "event.shiftKey" in content


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


def test_dashboard_shows_registrar_admin_shortcuts_for_authorized_staff(
    client,
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
    reg_grade_factory,
) -> None:
    """Registrar grade workflow should expose only permitted Django admin tables."""
    User = get_user_model()
    user = User.objects.create_user(
        "registrar_dashboard_admin",
        password="PassW0rd!",
        is_staff=True,
    )
    officer_group, _created = Group.objects.get_or_create(name="Registrar Officer")
    user.groups.add(officer_group)
    user.user_permissions.add(
        _perm("people", "view_student"),
        _perm("registry", "view_grade"),
    )
    _academic_year, _previous, current = reg_sem_pair_factory()
    section, curriculum = reg_sec_factory(
        current,
        course_number="305",
        curriculum_short_name="CURRI_REG_ADMIN",
    )
    student = reg_std_factory("registrar_dashboard_admin_student", curriculum, current)
    reg_grade_factory(student, section)

    client.force_login(user)
    response = client.get(reverse("reg_grades_dashboard"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Authorized database" in content
    assert reverse("admin:people_student_changelist") in content
    assert reverse("admin:registry_grade_changelist") in content
    assert reverse("admin:registry_registration_changelist") not in content
