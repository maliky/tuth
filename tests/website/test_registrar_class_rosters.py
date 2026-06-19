"""Registrar portal class-roster filters and read-only detail pages."""

from __future__ import annotations

from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission, User
from django.urls import reverse

from app.people.models.faculty import Faculty
from app.people.models.staffs import Staff
from app.people.models.student import Student
from app.registry.models.registration import Registration
from app.timetable.models.section import Section

pytestmark = pytest.mark.django_db


def _perm(app_label: str, codename: str) -> Permission:
    """Return a concrete model permission scoped by app label."""
    return Permission.objects.get(
        content_type__app_label=app_label,
        codename=codename,
    )


def _registrar_officer(username: str) -> User:
    """Create a registrar officer with the grade-view portal permission."""
    UserModel = get_user_model()
    user = UserModel.objects.create_user(username, password="PassW0rd!")
    officer_group, _created = Group.objects.get_or_create(name="Registrar Officer")
    grade_permission = _perm("registry", "view_grade")
    officer_group.permissions.add(grade_permission)
    user.user_permissions.add(grade_permission)
    user.groups.add(officer_group)
    return user


def _faculty(username: str, section: Section, first_name: str) -> Faculty:
    """Create a faculty profile assignable to a section."""
    user = User.objects.create_user(
        username,
        password="PassW0rd!",
        first_name=first_name,
        last_name="Teacher",
    )
    staff = Staff(user=user, position="Instructor")
    staff.save()
    faculty = Faculty(
        staff_profile=staff,
        college=section.curriculum_course.curriculum.college,
    )
    faculty.save()
    return faculty


def _course_code(section: Section) -> str:
    """Return the course code displayed in roster pages."""
    course = section.curriculum_course.course
    return course.short_code or course.code or str(course)


def _register_student(student: Student, section: Section) -> None:
    """Attach one student to a section roster."""
    Registration.objects.create(student=student, section=section)


def test_registrar_officer_filters_rosters_by_student_faculty_and_semester(
    client,
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
    reg_grade_factory,
) -> None:
    """Registrar officers should find class rosters without opening Django admin."""
    officer = _registrar_officer("reg_roster_filter")
    _academic_year, previous, current = reg_sem_pair_factory()
    visible_section, curriculum = reg_sec_factory(
        current,
        course_number="801",
        curriculum_short_name="CURRI_REG_ROSTER",
    )
    hidden_section, _hidden_curriculum = reg_sec_factory(
        previous,
        course_number="802",
        curriculum_short_name="CURRI_REG_ROSTER",
    )
    visible_faculty = _faculty("roster_visible_faculty", visible_section, "Visible")
    hidden_faculty = _faculty("roster_hidden_faculty", hidden_section, "Hidden")
    visible_section.faculty = visible_faculty
    visible_section.save(update_fields=["faculty"])
    hidden_section.faculty = hidden_faculty
    hidden_section.save(update_fields=["faculty"])
    student = reg_std_factory("registrar_roster_student", curriculum, current)
    hidden_student = reg_std_factory("registrar_roster_hidden", curriculum, previous)
    student.gender = "f"
    student.birth_date = date(2000, 1, 1)
    student.save(update_fields=["gender", "birth_date"])
    _register_student(student, visible_section)
    _register_student(hidden_student, hidden_section)
    reg_grade_factory(student, visible_section)
    reg_grade_factory(hidden_student, hidden_section)

    client.force_login(officer)
    response = client.get(
        reverse("reg_class_rosters"),
        {
            "student_id": str(student.id),
            "faculty_id": str(visible_faculty.id),
            "semester": str(current.id),
        },
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert _course_code(visible_section) in content
    assert _course_code(hidden_section) not in content
    assert reverse("reg_class_roster_detail", args=[visible_section.id]) in content
    assert "Class rosters" in content

    detail = client.get(reverse("reg_class_roster_detail", args=[visible_section.id]))
    detail_content = detail.content.decode()

    assert detail.status_code == 200
    assert student.student_id in detail_content
    assert "Female" in detail_content
    assert str(student.age) in detail_content
    assert "IP" in detail_content
    assert "Submitted" in detail_content


def test_registrar_roster_faculty_autocomplete_returns_assigned_faculty(
    client,
    reg_sem_pair_factory,
    reg_sec_factory,
) -> None:
    """Faculty lookup should support the registrar roster filter."""
    officer = _registrar_officer("reg_roster_faculty_lookup")
    _academic_year, _previous, current = reg_sem_pair_factory()
    section, _curriculum = reg_sec_factory(
        current,
        course_number="803",
        curriculum_short_name="CURRI_REG_FAC_LOOKUP",
    )
    faculty = _faculty("roster_lookup_faculty", section, "Lookup")

    client.force_login(officer)
    response = client.get(reverse("reg_faculty_autocomplete"), {"q": "Lookup"})
    payload = response.json()["results"]

    assert response.status_code == 200
    assert payload[0]["id"] == faculty.id
    assert "Lookup Teacher" in payload[0]["text"]


def test_grade_view_permission_without_registrar_role_cannot_open_rosters(
    client,
) -> None:
    """The portal roster route should be both permission- and role-gated."""
    UserModel = get_user_model()
    user = UserModel.objects.create_user("grade_perm_no_registrar", password="PassW0rd!")
    user.user_permissions.add(_perm("registry", "view_grade"))

    client.force_login(user)
    response = client.get(reverse("reg_class_rosters"))

    assert response.status_code == 403
