"""Admin scoping tests for faculty grade maintenance."""

from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.models import Permission, User
from django.test import RequestFactory
from typing import cast

import pytest

from app.people.admin.student_admin import StdAdmin
from app.people.models.student import Student
from app.registry.admin.grade_admin import GradeAdmin
from app.registry.models.grade import Grade
from app.registry.models.registration import Registration
from app.shared.auth.perms import UserRole
from app.timetable.models.section import Section


def _grade_permission(codename: str) -> Permission:
    """Return a registry grade permission by codename."""
    return Permission.objects.get(
        codename=codename,
        content_type__app_label="registry",
        content_type__model="grade",
    )


def _admin_request(user: User):
    """Return an admin-like request carrying the acting user."""
    request = RequestFactory().get("/admin/registry/grade/")
    request.user = user
    return request


def _student_autocomplete_request(user: User, section_id: int | None = None):
    """Return a Student admin autocomplete request for Grade.student."""
    query = {
        "app_label": "registry",
        "model_name": "grade",
        "field_name": "student",
    }
    if section_id is not None:
        query["section"] = str(section_id)
    request = RequestFactory().get("/admin/autocomplete/", data=query)
    request.user = user
    return request


def _faculty_grade_user(faculty) -> User:
    """Make a faculty user capable of opening grade admin."""
    user = cast(User, faculty.staff_profile.user)
    user.is_staff = True
    user.user_permissions.add(
        _grade_permission("add_grade"),
        _grade_permission("change_grade"),
        _grade_permission("view_grade"),
    )
    user.save(update_fields=["is_staff"])
    return user


def _make_grade(faculty, sec_factory, std_factory, suffix: str) -> Grade:
    """Create a grade row in a section owned by faculty."""
    section = sec_factory(f"79{suffix}", f"CURRI_GRADE_ADMIN_{suffix}", 1, 1)
    section.faculty = faculty
    section.save(update_fields=["faculty"])
    student = std_factory(
        f"grade_admin_student_{suffix}",
        f"CURRI_GRADE_ADMIN_{suffix}",
    )
    Registration.objects.create(student=student, section=section)
    return Grade.objects.create(student=student, section=section)


@pytest.mark.django_db
def test_grade_admin_faculty_queryset_is_limited_to_own_sections(
    faculty,
    faculty_factory,
    sec_factory,
    std_factory,
) -> None:
    """Faculty grade admin should expose only grades from assigned sections."""
    own_grade = _make_grade(faculty, sec_factory, std_factory, "1")
    other_grade = _make_grade(
        faculty_factory("grade_admin_other_faculty"),
        sec_factory,
        std_factory,
        "2",
    )
    user = _faculty_grade_user(faculty)
    admin_obj = GradeAdmin(Grade, admin.site)

    grade_ids = set(
        admin_obj.get_queryset(_admin_request(user)).values_list("id", flat=True)
    )

    assert own_grade.id in grade_ids
    assert other_grade.id not in grade_ids


@pytest.mark.django_db
def test_grade_admin_faculty_object_permissions_are_section_scoped(
    faculty,
    faculty_factory,
    sec_factory,
    std_factory,
) -> None:
    """Faculty users should not change another instructor's grade row."""
    own_grade = _make_grade(faculty, sec_factory, std_factory, "3")
    other_grade = _make_grade(
        faculty_factory("grade_admin_other_faculty_perm"),
        sec_factory,
        std_factory,
        "4",
    )
    user = _faculty_grade_user(faculty)
    request = _admin_request(user)
    admin_obj = GradeAdmin(Grade, admin.site)

    assert admin_obj.has_change_permission(request, own_grade) is True
    assert admin_obj.has_change_permission(request, other_grade) is False


@pytest.mark.django_db
def test_grade_admin_faculty_section_field_choices_are_scoped(
    faculty,
    faculty_factory,
    sec_factory,
    std_factory,
) -> None:
    """Faculty grade admin add form should only offer owned sections."""
    own_grade = _make_grade(faculty, sec_factory, std_factory, "5")
    other_grade = _make_grade(
        faculty_factory("grade_admin_other_faculty_field"),
        sec_factory,
        std_factory,
        "6",
    )
    user = _faculty_grade_user(faculty)
    request = _admin_request(user)
    admin_obj = GradeAdmin(Grade, admin.site)
    field = Grade._meta.get_field("section")

    formfield = admin_obj.formfield_for_foreignkey(field, request)
    section_ids = set(formfield.queryset.values_list("id", flat=True))

    assert own_grade.section_id in section_ids
    assert other_grade.section_id not in section_ids


@pytest.mark.django_db
def test_grade_admin_registrar_officer_bypasses_faculty_scope(
    faculty,
    faculty_factory,
    sec_factory,
    std_factory,
) -> None:
    """Registrar officer grade admin should still see all grades."""
    own_grade = _make_grade(faculty, sec_factory, std_factory, "7")
    other_grade = _make_grade(
        faculty_factory("grade_admin_other_registrar"),
        sec_factory,
        std_factory,
        "8",
    )
    user = User.objects.create_user("grade_admin_registrar", is_staff=True)
    group = UserRole.REGISTRAR_OFFICER.value.group
    group.permissions.add(_grade_permission("view_grade"))
    user.groups.add(group)
    admin_obj = GradeAdmin(Grade, admin.site)

    grade_ids = set(
        admin_obj.get_queryset(_admin_request(user)).values_list("id", flat=True)
    )

    assert {own_grade.id, other_grade.id}.issubset(grade_ids)


@pytest.mark.django_db
def test_grade_student_autocomplete_faculty_sees_only_own_section_students(
    faculty,
    faculty_factory,
    sec_factory,
    std_factory,
) -> None:
    """Grade.student autocomplete should not leak another faculty roster."""
    own_grade = _make_grade(faculty, sec_factory, std_factory, "9")
    own_second_grade = _make_grade(faculty, sec_factory, std_factory, "10")
    other_grade = _make_grade(
        faculty_factory("grade_admin_other_student_lookup"),
        sec_factory,
        std_factory,
        "11",
    )
    user = _faculty_grade_user(faculty)
    admin_obj = StdAdmin(Student, admin.site)

    student_ids = set(
        admin_obj.get_queryset(_student_autocomplete_request(user)).values_list(
            "id",
            flat=True,
        )
    )

    assert {own_grade.student_id, own_second_grade.student_id}.issubset(student_ids)
    assert other_grade.student_id not in student_ids


@pytest.mark.django_db
def test_grade_student_autocomplete_selected_section_narrows_faculty_students(
    faculty,
    sec_factory,
    std_factory,
) -> None:
    """Selecting a section should narrow Grade.student autocomplete to that roster."""
    own_grade = _make_grade(faculty, sec_factory, std_factory, "12")
    own_second_grade = _make_grade(faculty, sec_factory, std_factory, "13")
    user = _faculty_grade_user(faculty)
    admin_obj = StdAdmin(Student, admin.site)

    student_ids = set(
        admin_obj.get_queryset(
            _student_autocomplete_request(user, own_grade.section_id),
        ).values_list("id", flat=True)
    )

    assert own_grade.student_id in student_ids
    assert own_second_grade.student_id not in student_ids


@pytest.mark.django_db
def test_grade_student_autocomplete_selected_unowned_section_returns_none(
    faculty,
    faculty_factory,
    sec_factory,
    std_factory,
) -> None:
    """Faculty users should not inspect students from an unowned selected section."""
    own_grade = _make_grade(faculty, sec_factory, std_factory, "14")
    other_grade = _make_grade(
        faculty_factory("grade_admin_unowned_lookup"),
        sec_factory,
        std_factory,
        "15",
    )
    user = _faculty_grade_user(faculty)
    admin_obj = StdAdmin(Student, admin.site)

    student_ids = set(
        admin_obj.get_queryset(
            _student_autocomplete_request(user, other_grade.section_id),
        ).values_list("id", flat=True)
    )

    assert own_grade.student_id not in student_ids
    assert other_grade.student_id not in student_ids


@pytest.mark.django_db
def test_grade_student_autocomplete_registrar_section_scope_keeps_selected_roster(
    faculty,
    faculty_factory,
    sec_factory,
    std_factory,
) -> None:
    """Registrar roles may search the student roster for the selected section."""
    own_grade = _make_grade(faculty, sec_factory, std_factory, "16")
    other_grade = _make_grade(
        faculty_factory("grade_admin_registrar_student_lookup"),
        sec_factory,
        std_factory,
        "17",
    )
    user = User.objects.create_user("grade_admin_student_registrar", is_staff=True)
    group = UserRole.REGISTRAR_OFFICER.value.group
    group.permissions.add(_grade_permission("view_grade"))
    user.groups.add(group)
    admin_obj = StdAdmin(Student, admin.site)

    student_ids = set(
        admin_obj.get_queryset(
            _student_autocomplete_request(user, other_grade.section_id),
        ).values_list("id", flat=True)
    )

    assert own_grade.student_id not in student_ids
    assert other_grade.student_id in student_ids
