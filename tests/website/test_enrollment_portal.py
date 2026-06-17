"""Enrollment portal directory, intake, and shortcut regressions."""

from __future__ import annotations

from datetime import date, datetime

import pytest
from django.contrib.auth.models import Group, Permission, User
from django.urls import reverse

from app.academics.models.college import College
from app.academics.models.curriculum import Curriculum
from app.people.models.student import Student
from app.people.models.student_curriculum_enrollment import set_primary_std_curri_enroll
from app.registry.models.credit_hours import CreditHour
from app.registry.models.grade import Grade, GradeValue
from app.timetable.models.section import Section

pytestmark = pytest.mark.django_db


def _group_user(user: User, group_name: str) -> None:
    """Attach a user to a role group."""
    group, _created = Group.objects.get_or_create(name=group_name)
    user.groups.add(group)


def _perm(app_label: str, codename: str) -> Permission:
    """Return a concrete model permission scoped by app label."""
    return Permission.objects.get(
        content_type__app_label=app_label,
        codename=codename,
    )


def _student(
    username: str,
    student_id: str,
    curriculum: Curriculum,
    semester,
) -> Student:
    """Create a student attached to one primary curriculum."""
    user = User.objects.create_user(
        username=username,
        first_name=username.title(),
        last_name="Student",
    )
    student = Student(
        user=user,
        student_id=student_id,
        entry_semester=semester,
        last_enrolled_semester=semester,
    )
    student.save()
    set_primary_std_curri_enroll(student, curriculum, entry_semester_id=semester.id)
    return student


def _credit_hour(code: int) -> CreditHour:
    """Return a credit-hour lookup row for enrollment portal tests."""
    credit_hour, _created = CreditHour.objects.get_or_create(
        code=code,
        defaults={"label": str(code)},
    )
    return credit_hour


def _grade_value(code: str) -> GradeValue:
    """Return a normalized grade value for enrollment portal tests."""
    grade_value, _created = GradeValue.objects.get_or_create(code=code.lower())
    return grade_value


@pytest.fixture
def enrollment_user() -> User:
    """Return an enrollment user with student portal permissions."""
    user = User.objects.create_user("enrollment_portal", password="PassW0rd!")
    _group_user(user, "Enrollment")
    user.user_permissions.add(_perm("people", "view_student"))
    return user


def test_enrollment_dashboard_uses_sidebar_without_action_chips(client) -> None:
    """Enrollment dashboard should not duplicate sidebar tasks in the right panel."""
    user = User.objects.create_user("enrollment_dash", password="PassW0rd!")
    _group_user(user, "Enrollment")
    client.force_login(user)

    response = client.get(reverse("staff_role_dashboard", args=["enrollment"]))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Student directory" in content
    assert "Student snapshot" not in content
    assert "What can I do here?" not in content


def test_enrollment_officer_only_sees_authorized_admin_shortcuts(client) -> None:
    """Only enrollment officers should see permission-gated admin shortcuts."""
    officer = User.objects.create_user(
        "enrollment_officer_shortcuts",
        password="PassW0rd!",
        is_staff=True,
    )
    _group_user(officer, "Enrollment Officer")
    officer.user_permissions.add(_perm("people", "view_student"))
    client.force_login(officer)

    officer_response = client.get(
        reverse("staff_role_dashboard", args=["enrollment_officer"])
    )
    officer_content = officer_response.content.decode()

    assert officer_response.status_code == 200
    assert "Authorized database" in officer_content
    assert reverse("admin:people_student_changelist") in officer_content

    clerk = User.objects.create_user(
        "enrollment_clerk_shortcuts",
        password="PassW0rd!",
        is_staff=True,
    )
    _group_user(clerk, "Enrollment")
    clerk.user_permissions.add(_perm("people", "view_student"))
    client.force_login(clerk)

    clerk_response = client.get(reverse("staff_role_dashboard", args=["enrollment"]))

    assert clerk_response.status_code == 200
    assert "Authorized database" not in clerk_response.content.decode()


def test_student_directory_filters_by_name_college_program_and_semester(
    client,
    enrollment_user,
    curriculum,
    sem_factory,
) -> None:
    """Directory filters should narrow records by the requested student dimensions."""
    semester = sem_factory(1, datetime(2026, 1, 1))
    other_college = College.objects.create(code="TCOL", long_name="Test College")
    other_curriculum = Curriculum.objects.create(
        short_name="T-PROG",
        long_name="Test Program",
        college=other_college,
    )
    target = _student("alpha", "DIR1001", other_curriculum, semester)
    other = _student("beta", "DIR2002", curriculum, semester)
    client.force_login(enrollment_user)

    response = client.get(
        reverse("std_list"),
        {
            "q": "alpha",
            "college": str(other_college.id),
            "program": str(other_curriculum.id),
            "semester": str(semester.id),
        },
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert "Student directory" in content
    assert target.student_id in content
    assert other.student_id not in content


def test_student_intake_persists_expanded_profile_fields(
    client,
    curriculum,
    sem_factory,
) -> None:
    """Portal intake should save the richer student profile without a second form."""
    semester = sem_factory(1, datetime(2026, 1, 1))
    user = User.objects.create_user("enrollment_intake", password="PassW0rd!")
    _group_user(user, "Enrollment")
    user.user_permissions.add(
        _perm("people", "add_student"), _perm("people", "view_student")
    )
    client.force_login(user)

    response = client.post(
        reverse("create_std"),
        {
            "student_id": "INT1001",
            "prefix_name": "Miss.",
            "first_name": "Intake",
            "middle_name": "Middle",
            "last_name": "Student",
            "suffix_name": "Jr.",
            "email": "intake.student@example.test",
            "primary_curriculum": str(curriculum.id),
            "entry_semester": str(semester.id),
            "last_enrolled_semester": str(semester.id),
            "max_credit_hours": "21",
            "phone_number": "+231770000001",
            "physical_address": "Harper, Maryland County",
            "birth_date": "2000-02-03",
            "birth_place": "Harper",
            "gender": "f",
            "nationality": "Liberian",
            "origin_county": "Maryland",
            "marital_status": "Single",
            "last_school_attended": "Tubman High",
            "reason_for_leaving": "Graduated",
            "father_name": "Father Student",
            "father_address": "Father address",
            "mother_name": "Mother Student",
            "mother_address": "Mother address",
            "emergency_contact": "Emergency Person +231770000002",
        },
    )

    assert response.status_code == 302
    student = Student.objects.get(student_id="INT1001")
    assert student.middle_name == "Middle"
    assert student.prefix_name == "Miss."
    assert student.max_credit_hours == 21
    assert str(student.phone_number) == "+231770000001"
    assert student.birth_date == date(2000, 2, 3)
    assert student.last_school_attended == "Tubman High"
    assert student.emergency_contact == "Emergency Person +231770000002"


def test_student_and_program_autocomplete_include_richer_context(
    client,
    enrollment_user,
    curriculum,
    sem_factory,
) -> None:
    """Autocomplete endpoints should expose student and program context."""
    semester = sem_factory(1, datetime(2026, 1, 1))
    student = _student("lookup", "LOOK1001", curriculum, semester)
    client.force_login(enrollment_user)

    student_response = client.get(
        reverse("std_autocomplete"), {"q": curriculum.short_name}
    )
    program_response = client.get(
        reverse("curriculum_autocomplete"), {"q": curriculum.short_name}
    )

    assert student_response.status_code == 200
    student_payload = student_response.json()["results"]
    assert student_payload[0]["pk"] == student.pk
    assert student_payload[0]["college"] == curriculum.college.code
    assert student_payload[0]["semester"] == str(semester)

    assert program_response.status_code == 200
    program_payload = program_response.json()["results"]
    assert program_payload[0]["id"] == curriculum.id
    assert curriculum.short_name in program_payload[0]["text"]


def test_student_detail_shows_level_from_completed_credits(
    client,
    enrollment_user,
    curriculum,
    curriculum_course_factory,
    sem_factory,
) -> None:
    """Student detail should show class level from passing credits."""
    semester = sem_factory(1, datetime(2026, 1, 1))
    student = _student("senior_detail", "SEN1001", curriculum, semester)

    for index in range(37):
        curriculum_course = curriculum_course_factory(
            f"8{index:02d}",
            curriculum.short_name,
        )
        curriculum_course.credit_hours = _credit_hour(3)
        curriculum_course.save(update_fields=["credit_hours"])
        section = Section.objects.create(
            curriculum_course=curriculum_course,
            semester=semester,
            number=1,
        )
        Grade.objects.create(student=student, section=section, value=_grade_value("a"))

    client.force_login(enrollment_user)
    response = client.get(reverse("std_detail", args=[student.pk]))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Class level" in content
    assert "senior" in content
