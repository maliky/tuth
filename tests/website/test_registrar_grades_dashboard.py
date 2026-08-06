"""Tests for registrar grades dashboard default semester selection."""

from __future__ import annotations

from typing import cast

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.urls import reverse

from app.academics.choices import AcademicCareer
from app.academics.models.curriculum import Curriculum
from app.registry.models.grade import Grade, GradeValue
from app.registry.models.registration import Registration
from app.timetable.models.semester import SemesterStatus

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


def _grant_grade_editor_perms(user) -> None:
    """Grant the model permissions required by the registrar grade editor."""
    user.user_permissions.add(
        _perm("registry", "add_grade"),
        _perm("registry", "change_grade"),
    )


def _set_career(student, curricula: list[Curriculum], career: str) -> None:
    """Place a student and related curricula in one academic career."""
    student.academic_career = career
    student.save(update_fields=["academic_career"])
    for curriculum in curricula:
        curriculum.academic_career = career
        curriculum.save(update_fields=["academic_career"])


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
    _set_career(
        previous_student,
        [curriculum],
        AcademicCareer.GRADUATE,
    )

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
    _set_career(
        current_student,
        [curriculum, _current_curriculum],
        AcademicCareer.GRADUATE,
    )

    client.force_login(user)
    response = client.get(reverse("reg_grades_dashboard"))

    assert response.status_code == 200
    assert _selected_sem_value(response) == "all"
    assert response.context["selected_academic_career"] == "graduate"
    assert len(response.context["student_groups"]) == 2


def test_dashboard_defaults_to_grad_students_and_can_show_all_careers(
    client,
    reg_user_factory,
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
    reg_grade_factory,
) -> None:
    """Registrar grade review should start in graduate scope, with all as opt-in."""
    user = reg_user_factory("registrar_dashboard_career_default")
    _academic_year, _previous, current = reg_sem_pair_factory()
    grad_section, grad_curriculum = reg_sec_factory(
        current,
        course_number="321",
        curriculum_short_name="CURRI_REG_GRAD",
    )
    grad_student = reg_std_factory("registrar_grad_student", grad_curriculum, current)
    reg_grade_factory(grad_student, grad_section)
    _set_career(grad_student, [grad_curriculum], AcademicCareer.GRADUATE)

    undergrad_section, undergrad_curriculum = reg_sec_factory(
        current,
        course_number="322",
        curriculum_short_name="CURRI_REG_UNDERGRAD",
    )
    undergrad_student = reg_std_factory(
        "registrar_undergrad_student",
        undergrad_curriculum,
        current,
    )
    reg_grade_factory(undergrad_student, undergrad_section)
    _set_career(
        undergrad_student,
        [undergrad_curriculum],
        AcademicCareer.UNDERGRADUATE,
    )

    client.force_login(user)
    default_response = client.get(reverse("reg_grades_dashboard"))
    all_response = client.get(
        reverse("reg_grades_dashboard"),
        {"academic_career": "all"},
    )

    default_ids = {
        group["student"].id for group in default_response.context["student_groups"]
    }
    all_ids = {group["student"].id for group in all_response.context["student_groups"]}
    assert default_response.status_code == 200
    assert default_response.context["selected_academic_career"] == "graduate"
    assert default_ids == {grad_student.id}
    assert all_ids == {grad_student.id, undergrad_student.id}


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
    response = client.get(
        reverse("reg_grades_dashboard"),
        {"semester": str(current.id), "academic_career": "all"},
    )
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
    assert "data-transcript-layout-select" not in content
    assert "Portrait" not in content
    assert "Landscape" not in content
    assert "event.shiftKey" in content


def test_dashboard_selected_student_shows_academic_snapshot_and_roster_link(
    client,
    reg_user_factory,
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
    reg_grade_factory,
) -> None:
    """Filtering to one student should expose registrar-relevant student context."""
    user = reg_user_factory("registrar_dashboard_student_snapshot")
    _academic_year, _previous, current = reg_sem_pair_factory()
    section, curriculum = reg_sec_factory(
        current,
        course_number="306",
        curriculum_short_name="CURRI_REG_SNAPSHOT",
    )
    student = reg_std_factory("registrar_snapshot_student", curriculum, current)
    reg_grade_factory(student, section)
    Registration.objects.create(student=student, section=section)

    client.force_login(user)
    response = client.get(
        reverse("reg_grades_dashboard"),
        {"student_id": str(student.id), "semester": "all", "academic_career": "all"},
    )
    snapshot = response.context["selected_student_snapshot"]
    username_row = next(row for row in snapshot["rows"] if row["label"] == "Username")
    content = response.content.decode()

    assert response.status_code == 200
    assert snapshot["student_id"] == student.student_id
    assert username_row["value"] == student.username[:15]
    assert username_row["title"] == student.username
    assert snapshot["rosters_url"] == (
        f"{reverse('reg_class_rosters')}?student_id={student.id}&semester=all"
        "&academic_career=all"
    )
    assert "Academic snapshot" in content
    assert f'title="{student.username}"' in content
    assert curriculum.short_name in content
    assert student.student_id in content
    assert reverse("reg_class_roster_detail", args=[section.id]) in content


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


def test_registrar_grade_sidebar_includes_class_rosters_for_registrar(
    client,
    reg_user_factory,
    reg_sem_pair_factory,
) -> None:
    """Registrar sidebar should expose class rosters without officer-only links."""
    user = reg_user_factory("registrar_sidebar_rosters")
    reg_sem_pair_factory()

    client.force_login(user)
    response = client.get(reverse("reg_grades_dashboard"))
    sidebar_links = response.context["sidebar_links"]
    content = response.content.decode()

    assert response.status_code == 200
    assert any(
        link["href"] == f"{reverse('reg_class_rosters')}?academic_career=graduate"
        for link in sidebar_links
    )
    assert "Class rosters" in content
    assert reverse("reg_crs_wins") not in {link["href"] for link in sidebar_links}


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


def test_dashboard_shows_grade_editor_for_authorized_registrar(
    client,
    reg_user_factory,
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
) -> None:
    """Authorized registrar users should see the semester grade editor action."""
    user = reg_user_factory("registrar_dashboard_grade_editor")
    _grant_grade_editor_perms(user)
    _academic_year, _previous, current = reg_sem_pair_factory()
    section, curriculum = reg_sec_factory(
        current,
        course_number="307",
        curriculum_short_name="CURRI_REG_EDITOR",
    )
    student = reg_std_factory("registrar_editor_student", curriculum, current)
    Registration.objects.create(student=student, section=section)

    client.force_login(user)
    response = client.get(
        reverse("reg_grades_dashboard"),
        {
            "student_id": str(student.id),
            "semester": str(current.id),
            "academic_career": "all",
        },
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert "Add/correct grades" in content
    assert "Needs grade" in content
    assert reverse("reg_grade_semester_editor", args=[student.id, current.id]) in content


def test_dashboard_hides_grade_editor_without_change_permissions(
    client,
    reg_user_factory,
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
    reg_grade_factory,
) -> None:
    """Grade viewers should not see mutation actions without add/change rights."""
    user = reg_user_factory("registrar_dashboard_grade_viewer")
    _academic_year, _previous, current = reg_sem_pair_factory()
    section, curriculum = reg_sec_factory(
        current,
        course_number="308",
        curriculum_short_name="CURRI_REG_VIEW_ONLY",
    )
    student = reg_std_factory("registrar_viewer_student", curriculum, current)
    reg_grade_factory(student, section)

    client.force_login(user)
    response = client.get(
        reverse("reg_grades_dashboard"),
        {
            "student_id": str(student.id),
            "semester": str(current.id),
            "academic_career": "all",
        },
    )

    assert response.status_code == 200
    assert "Add/correct grades" not in response.content.decode()


def test_registrar_grade_editor_get_does_not_create_missing_grade(
    client,
    reg_user_factory,
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
) -> None:
    """Opening the editor should list missing rows without mutating the DB."""
    user = reg_user_factory("registrar_editor_get")
    _grant_grade_editor_perms(user)
    _academic_year, _previous, current = reg_sem_pair_factory()
    section, curriculum = reg_sec_factory(
        current,
        course_number="309",
        curriculum_short_name="CURRI_REG_GET",
    )
    student = reg_std_factory("registrar_editor_get_student", curriculum, current)
    Registration.objects.create(student=student, section=section)

    client.force_login(user)
    response = client.get(
        reverse("reg_grade_semester_editor", args=[student.id, current.id])
    )

    assert response.status_code == 200
    assert "Save grade changes" in response.content.decode()
    assert not Grade.objects.filter(student=student, section=section).exists()


def test_registrar_grade_editor_post_creates_missing_grade(
    client,
    reg_user_factory,
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
) -> None:
    """Submitting a listed registration should create the missing grade row."""
    GradeValue._populate_attributes_and_db()
    user = reg_user_factory("registrar_editor_create")
    _grant_grade_editor_perms(user)
    _academic_year, _previous, current = reg_sem_pair_factory()
    section, curriculum = reg_sec_factory(
        current,
        course_number="310",
        curriculum_short_name="CURRI_REG_CREATE",
    )
    student = reg_std_factory("registrar_editor_create_student", curriculum, current)
    Registration.objects.create(student=student, section=section)

    client.force_login(user)
    response = client.post(
        reverse("reg_grade_semester_editor", args=[student.id, current.id]),
        {f"grade_section_{section.id}": "a"},
    )

    grade = Grade.objects.get(student=student, section=section)
    assert response.status_code == 302
    assert grade.value is not None
    assert grade.value.code == "a"
    assert "registrar_editor_create" in grade.info


def test_registrar_grade_editor_corrects_closed_semester_grade(
    client,
    reg_user_factory,
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
    reg_grade_factory,
) -> None:
    """Registrar override should work even when faculty grade entry is closed."""
    GradeValue._populate_attributes_and_db()
    user = reg_user_factory("registrar_editor_closed")
    _grant_grade_editor_perms(user)
    _academic_year, _previous, current = reg_sem_pair_factory()
    SemesterStatus._populate_attributes_and_db()
    current.status_id = "running"
    current.save(update_fields=["status"])
    section, curriculum = reg_sec_factory(
        current,
        course_number="311",
        curriculum_short_name="CURRI_REG_CLOSED",
    )
    student = reg_std_factory("registrar_editor_closed_student", curriculum, current)
    grade = reg_grade_factory(student, section)
    Registration.objects.create(student=student, section=section)

    client.force_login(user)
    response = client.post(
        reverse("reg_grade_semester_editor", args=[student.id, current.id]),
        {f"grade_section_{section.id}": "b"},
    )

    grade.refresh_from_db()
    assert response.status_code == 302
    assert grade.value is not None
    assert grade.value.code == "b"


def test_registrar_grade_editor_rejects_unlisted_section(
    client,
    reg_user_factory,
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
) -> None:
    """Posted section ids must belong to the visible student semester rows."""
    GradeValue._populate_attributes_and_db()
    user = reg_user_factory("registrar_editor_bad_section")
    _grant_grade_editor_perms(user)
    _academic_year, _previous, current = reg_sem_pair_factory()
    section, curriculum = reg_sec_factory(
        current,
        course_number="312",
        curriculum_short_name="CURRI_REG_BAD",
    )
    other_section, _other_curriculum = reg_sec_factory(
        current,
        course_number="313",
        curriculum_short_name="CURRI_REG_BAD",
    )
    student = reg_std_factory("registrar_editor_bad_student", curriculum, current)
    Registration.objects.create(student=student, section=section)

    client.force_login(user)
    response = client.post(
        reverse("reg_grade_semester_editor", args=[student.id, current.id]),
        {f"grade_section_{other_section.id}": "a"},
    )

    assert response.status_code == 400
    assert not Grade.objects.filter(student=student, section=other_section).exists()
