"""Read-only academic oversight for grade and class rosters."""

from __future__ import annotations

from datetime import date
from typing import cast

import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse

from app.academics.models.college import College
from app.academics.models.course import Course
from app.academics.models.curriculum import Curriculum
from app.academics.models.curriculum_course import CurriCrs
from app.academics.models.department import Department
from app.people.models.faculty import Faculty
from app.people.models.staffs import Staff
from app.people.models.student import Student
from app.registry.models.grade import Grade, GradeValue
from app.registry.models.registration import Registration
from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester, SemesterStatus

pytestmark = pytest.mark.django_db


def _group_user(user: User, group_name: str) -> None:
    """Attach a user to a role group."""
    group, _created = Group.objects.get_or_create(name=group_name)
    user.groups.add(group)


def _faculty_role_user(
    username: str,
    role_name: str,
    *,
    college: College,
    department: Department | None = None,
) -> tuple[User, Faculty]:
    """Create one role user with a staff and faculty profile."""
    user = User.objects.create_user(username, password="PassW0rd!")
    _group_user(user, role_name)
    staff = Staff(user=user, position=role_name, department=department)
    staff.save()
    faculty = Faculty(staff_profile=staff, college=college)
    faculty.save()
    return user, faculty


def _staff_role_user(username: str, role_name: str) -> User:
    """Create one staff-only role user."""
    user = User.objects.create_user(username, password="PassW0rd!")
    _group_user(user, role_name)
    staff = Staff(user=user, position=role_name)
    staff.save()
    return user


def _section(
    *,
    college: College,
    department_code: str,
    curriculum_code: str,
    course_number: str,
    faculty: Faculty,
    semester: Semester,
) -> Section:
    """Create a section with explicit college, department, course, and faculty."""
    department, _created = Department.objects.get_or_create(
        code=department_code,
        defaults={"college": college},
    )
    course = Course.objects.create(
        department=department,
        number=course_number,
        title=f"{department_code} Course {course_number}",
    )
    curriculum = Curriculum.objects.create(
        short_name=curriculum_code,
        long_name=curriculum_code,
        college=college,
    )
    curriculum_course = CurriCrs.objects.create(curriculum=curriculum, course=course)
    return Section.objects.create(
        curriculum_course=curriculum_course,
        semester=semester,
        faculty=faculty,
        number=1,
    )


def _registered_grade(section: Section, username: str, grade_code: str) -> Student:
    """Create one registered student with a submitted grade."""
    GradeValue._populate_attributes_and_db()
    student = Student.objects.create(
        username=username,
        first_name=username.title(),
        last_name="Student",
        student_id=f"SID-{username.upper()}",
    )
    Registration.objects.create(student=student, section=section)
    Grade.objects.create(
        student=student,
        section=section,
        value=GradeValue.objects.get(code=grade_code),
    )
    return cast(Student, student)


@pytest.fixture
def oversight_semester() -> Semester:
    """Return one semester open for grade-entry visibility tests."""
    SemesterStatus._populate_attributes_and_db()
    academic_year = AcademicYear.objects.create(start_date=date(2026, 1, 1))
    semester = Semester.objects.create(
        academic_year=academic_year,
        number=1,
        status_id="grade_entry",
    )
    return semester


def test_chair_sees_department_roster_and_grade_detail(client, oversight_semester):
    """Chair oversight should include own-department rosters only."""
    college = College.objects.create(code="CCHAIR", long_name="Chair College")
    chair_department = Department.objects.create(code="CHD", college=college)
    chair_user, chair_faculty = _faculty_role_user(
        "chair_roster",
        "Chair",
        college=college,
        department=chair_department,
    )
    _other_user, other_faculty = _faculty_role_user(
        "chair_other_faculty",
        "Faculty",
        college=college,
    )
    visible_section = _section(
        college=college,
        department_code="CHD",
        curriculum_code="CUR-CHAIR",
        course_number="501",
        faculty=chair_faculty,
        semester=oversight_semester,
    )
    hidden_section = _section(
        college=college,
        department_code="OTH",
        curriculum_code="CUR-OTHER",
        course_number="502",
        faculty=other_faculty,
        semester=oversight_semester,
    )
    student = _registered_grade(visible_section, "chair_visible", "a")
    _registered_grade(hidden_section, "chair_hidden", "b")

    client.force_login(chair_user)
    response = client.get(reverse("staff_grade_rosters", args=["chair"]))
    content = response.content.decode()

    assert response.status_code == 200
    assert "CHD501" in content
    assert "OTH502" not in content
    assert reverse("staff_grade_roster_detail", args=["chair", visible_section.id]) in (
        content
    )

    detail = client.get(
        reverse("staff_grade_roster_detail", args=["chair", visible_section.id])
    )
    detail_content = detail.content.decode()

    assert detail.status_code == 200
    assert student.student_id in detail_content
    assert "A" in detail_content
    assert (
        client.get(
            reverse("staff_grade_roster_detail", args=["chair", hidden_section.id])
        ).status_code
        == 404
    )


def test_dean_sees_college_rosters_not_other_colleges(client, oversight_semester):
    """Dean oversight should be limited to the dean's college."""
    college = College.objects.create(code="CDEAN", long_name="Dean College")
    other_college = College.objects.create(code="CODEAN", long_name="Other College")
    dean_user, _dean_faculty = _faculty_role_user(
        "dean_roster",
        "Dean",
        college=college,
    )
    _fac_user, faculty = _faculty_role_user(
        "dean_faculty",
        "Faculty",
        college=college,
    )
    _other_user, other_faculty = _faculty_role_user(
        "dean_other_faculty",
        "Faculty",
        college=other_college,
    )
    visible_section = _section(
        college=college,
        department_code="DND",
        curriculum_code="CUR-DEAN",
        course_number="601",
        faculty=faculty,
        semester=oversight_semester,
    )
    hidden_section = _section(
        college=other_college,
        department_code="OND",
        curriculum_code="CUR-OUT",
        course_number="602",
        faculty=other_faculty,
        semester=oversight_semester,
    )

    client.force_login(dean_user)
    response = client.get(reverse("staff_grade_rosters", args=["dean"]))
    content = response.content.decode()

    assert response.status_code == 200
    assert "DND601" in content
    assert "OND602" not in content
    assert (
        client.get(
            reverse("staff_grade_roster_detail", args=["dean", visible_section.id])
        ).status_code
        == 200
    )
    assert (
        client.get(
            reverse("staff_grade_roster_detail", args=["dean", hidden_section.id])
        ).status_code
        == 404
    )


def test_vpaa_sees_institution_rosters(client, oversight_semester):
    """VPAA oversight should see rosters across colleges."""
    college = College.objects.create(code="CVPA", long_name="VPAA College")
    other_college = College.objects.create(code="CVPB", long_name="Other VPAA College")
    vpaa_user = _staff_role_user("vpaa_roster", "VPAA")
    _fac_user, faculty = _faculty_role_user(
        "vpaa_faculty",
        "Faculty",
        college=college,
    )
    _other_user, other_faculty = _faculty_role_user(
        "vpaa_other_faculty",
        "Faculty",
        college=other_college,
    )
    first_section = _section(
        college=college,
        department_code="VPA",
        curriculum_code="CUR-VPA",
        course_number="701",
        faculty=faculty,
        semester=oversight_semester,
    )
    second_section = _section(
        college=other_college,
        department_code="VPB",
        curriculum_code="CUR-VPB",
        course_number="702",
        faculty=other_faculty,
        semester=oversight_semester,
    )

    client.force_login(vpaa_user)
    response = client.get(reverse("staff_grade_rosters", args=["vpaa"]))
    content = response.content.decode()

    assert response.status_code == 200
    assert "VPA701" in content
    assert "VPB702" in content
    assert (
        client.get(
            reverse("staff_grade_roster_detail", args=["vpaa", first_section.id])
        ).status_code
        == 200
    )
    assert (
        client.get(
            reverse("staff_grade_roster_detail", args=["vpaa", second_section.id])
        ).status_code
        == 200
    )


def test_faculty_cannot_open_academic_oversight_route(client):
    """Faculty grade entry stays separate from leadership oversight."""
    college = College.objects.create(code="CFAC", long_name="Faculty College")
    faculty_user, _faculty = _faculty_role_user(
        "faculty_no_oversight",
        "Faculty",
        college=college,
    )
    client.force_login(faculty_user)

    response = client.get(reverse("staff_grade_rosters", args=["dean"]))

    assert response.status_code == 403
