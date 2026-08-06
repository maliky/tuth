"""Registrar portal class-roster filters and read-only detail pages."""

from __future__ import annotations

from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission, User
from django.urls import reverse

from app.academics.choices import AcademicCareer
from app.academics.models.curriculum import Curriculum
from app.people.models.faculty import Faculty
from app.people.models.staffs import Staff
from app.people.models.student import Student
from app.registry.models.registration import Registration
from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester, SemesterStatus

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


def _set_career(
    curriculum: Curriculum,
    career: str,
    *students: Student,
) -> None:
    """Move one curriculum and optional students into an academic career."""
    curriculum.academic_career = career
    curriculum.save(update_fields=["academic_career"])
    for student in students:
        student.academic_career = career
        student.save(update_fields=["academic_career"])


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
        curriculum_short_name="CURRI_REG_ROSTER_HIDDEN",
    )
    visible_faculty = _faculty("roster_visible_faculty", visible_section, "Visible")
    hidden_faculty = _faculty("roster_hidden_faculty", hidden_section, "Hidden")
    visible_section.faculty = visible_faculty
    visible_section.save(update_fields=["faculty"])
    hidden_section.faculty = hidden_faculty
    hidden_section.save(update_fields=["faculty"])
    student = reg_std_factory("registrar_roster_student", curriculum, current)
    hidden_student = reg_std_factory("registrar_roster_hidden", curriculum, previous)
    _set_career(curriculum, AcademicCareer.GRADUATE, student, hidden_student)
    _set_career(_hidden_curriculum, AcademicCareer.UNDERGRADUATE)
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


def test_registrar_rosters_default_to_graduate_sections_and_all_opt_in(
    client,
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
) -> None:
    """Graduate roster scope should hide undergraduate sections until all is selected."""
    officer = _registrar_officer("reg_roster_career_scope")
    _academic_year, _previous, current = reg_sem_pair_factory()
    graduate_section, graduate_curriculum = reg_sec_factory(
        current,
        course_number="811",
        curriculum_short_name="CURRI_REG_GRAD_ROSTER",
    )
    undergrad_section, undergrad_curriculum = reg_sec_factory(
        current,
        course_number="812",
        curriculum_short_name="CURRI_REG_UNDER_ROSTER",
    )
    graduate_student = reg_std_factory(
        "registrar_roster_grad_student",
        graduate_curriculum,
        current,
    )
    undergrad_student = reg_std_factory(
        "registrar_roster_under_student",
        undergrad_curriculum,
        current,
    )
    _set_career(graduate_curriculum, AcademicCareer.GRADUATE, graduate_student)
    _set_career(undergrad_curriculum, AcademicCareer.UNDERGRADUATE, undergrad_student)
    _register_student(graduate_student, graduate_section)
    _register_student(undergrad_student, undergrad_section)

    client.force_login(officer)
    default_response = client.get(reverse("reg_class_rosters"))
    all_response = client.get(
        reverse("reg_class_rosters"),
        {"academic_career": "all"},
    )

    default_content = default_response.content.decode()
    all_content = all_response.content.decode()
    assert default_response.status_code == 200
    assert default_response.context["selected_academic_career"] == "graduate"
    assert _course_code(graduate_section) in default_content
    assert _course_code(undergrad_section) not in default_content
    assert _course_code(graduate_section) in all_content
    assert _course_code(undergrad_section) in all_content

    undergrad_detail_default = client.get(
        reverse("reg_class_roster_detail", args=[undergrad_section.id])
    )
    undergrad_detail_all = client.get(
        reverse("reg_class_roster_detail", args=[undergrad_section.id]),
        {"academic_career": "all"},
    )

    assert undergrad_detail_default.status_code == 404
    assert undergrad_detail_all.status_code == 200


def test_registrar_rosters_hide_pre_launch_semesters_for_graduate(
    client,
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
) -> None:
    """Graduate roster filters should begin at academic year 26-27."""
    officer = _registrar_officer("reg_roster_grad_launch_floor")
    _academic_year, _previous, current = reg_sem_pair_factory(today=date(2025, 9, 1))
    SemesterStatus._populate_attributes_and_db()
    launch_year, _created = AcademicYear.objects.get_or_create(
        start_date=date(2026, 8, 1)
    )
    launch_semester = Semester.objects.create(
        academic_year=launch_year,
        number=1,
        academic_career=AcademicCareer.GRADUATE,
        status_id="planning",
    )
    old_section, old_curriculum = reg_sec_factory(
        current,
        course_number="831",
        curriculum_short_name="CURRI_REG_OLD_GRAD",
    )
    launch_section, launch_curriculum = reg_sec_factory(
        launch_semester,
        course_number="832",
        curriculum_short_name="CURRI_REG_NEW_GRAD",
    )
    old_student = reg_std_factory("old_grad_roster_student", old_curriculum, current)
    launch_student = reg_std_factory(
        "launch_grad_roster_student",
        launch_curriculum,
        launch_semester,
    )
    _set_career(old_curriculum, AcademicCareer.GRADUATE, old_student)
    _set_career(launch_curriculum, AcademicCareer.GRADUATE, launch_student)
    _register_student(old_student, old_section)
    _register_student(launch_student, launch_section)

    client.force_login(officer)
    response = client.get(reverse("reg_class_rosters"), {"academic_career": "graduate"})
    content = response.content.decode()
    semester_labels = [option["label"] for option in response.context["semester_options"]]

    assert response.status_code == 200
    assert _course_code(launch_section) in content
    assert _course_code(old_section) not in content
    assert any("26-27" in label for label in semester_labels)
    assert all("25-26" not in label for label in semester_labels)


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
    _set_career(_curriculum, AcademicCareer.GRADUATE)
    faculty = _faculty("roster_lookup_faculty", section, "Lookup")
    section.faculty = faculty
    section.save(update_fields=["faculty"])

    client.force_login(officer)
    response = client.get(reverse("reg_faculty_autocomplete"), {"q": "Lookup"})
    payload = response.json()["results"]

    assert response.status_code == 200
    assert payload[0]["id"] == faculty.id
    assert "Lookup Teacher" in payload[0]["text"]


def test_registrar_roster_autocomplete_obeys_academic_career(
    client,
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
) -> None:
    """Roster autocomplete should not suggest people outside the selected career."""
    officer = _registrar_officer("reg_roster_career_autocomplete")
    _academic_year, _previous, current = reg_sem_pair_factory()
    graduate_section, graduate_curriculum = reg_sec_factory(
        current,
        course_number="821",
        curriculum_short_name="CURRI_REG_GRAD_AUTO",
    )
    undergrad_section, undergrad_curriculum = reg_sec_factory(
        current,
        course_number="822",
        curriculum_short_name="CURRI_REG_UNDER_AUTO",
    )
    graduate_faculty = _faculty("roster_grad_faculty", graduate_section, "CareerScope")
    undergrad_faculty = _faculty(
        "roster_under_faculty",
        undergrad_section,
        "CareerScope",
    )
    graduate_section.faculty = graduate_faculty
    graduate_section.save(update_fields=["faculty"])
    undergrad_section.faculty = undergrad_faculty
    undergrad_section.save(update_fields=["faculty"])
    graduate_student = reg_std_factory(
        "career_scope_grad_student",
        graduate_curriculum,
        current,
    )
    undergrad_student = reg_std_factory(
        "career_scope_under_student",
        undergrad_curriculum,
        current,
    )
    _set_career(graduate_curriculum, AcademicCareer.GRADUATE, graduate_student)
    _set_career(undergrad_curriculum, AcademicCareer.UNDERGRADUATE, undergrad_student)
    _register_student(graduate_student, graduate_section)
    _register_student(undergrad_student, undergrad_section)

    client.force_login(officer)
    faculty_response = client.get(
        reverse("reg_faculty_autocomplete"),
        {"q": "CareerScope", "academic_career": "graduate"},
    )
    student_response = client.get(
        reverse("reg_std_autocomplete"),
        {"q": "career_scope", "academic_career": "graduate"},
    )

    faculty_ids = {item["id"] for item in faculty_response.json()["results"]}
    student_ids = {item["id"] for item in student_response.json()["results"]}
    assert graduate_faculty.id in faculty_ids
    assert undergrad_faculty.id not in faculty_ids
    assert graduate_student.id in student_ids
    assert undergrad_student.id not in student_ids


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
