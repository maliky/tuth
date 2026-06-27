"""Academic dashboard coverage for dean and chair workspaces."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse
from django.utils.text import slugify

from app.academics.models.college import College
from app.academics.models.course import Course
from app.academics.models.curriculum import CurriStatus, Curriculum
from app.academics.models.curriculum_course import CurriCrs
from app.academics.models.department import Department
from app.people.models.faculty import Faculty
from app.people.models.staffs import Staff
from app.people.models.student import Student
from app.registry.models.registration import Registration
from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester, SemesterStatus

pytestmark = pytest.mark.django_db


def _group_user(user: User, group_name: str) -> None:
    """Attach a user to one role group."""
    group, _created = Group.objects.get_or_create(name=group_name)
    user.groups.add(group)


def _semester() -> Semester:
    """Return one deterministic dashboard semester."""
    SemesterStatus._populate_attributes_and_db()
    academic_year = AcademicYear.objects.create(start_date=date(2025, 8, 1))
    return Semester.objects.create(
        academic_year=academic_year,
        number=1,
        status_id="running",
    )


def _faculty_user(
    username: str,
    role_name: str,
    *,
    college: College,
    department: Department | None = None,
) -> tuple[User, Faculty]:
    """Create a role user with staff and faculty profiles."""
    user = User.objects.create_user(
        username,
        password="PassW0rd!",
        first_name=username.replace("_", " ").title(),
        last_name=role_name,
    )
    _group_user(user, role_name)
    staff = Staff(user=user, position=role_name, department=department)
    staff.save()
    faculty = Faculty(staff_profile=staff, college=college)
    faculty.save()
    return user, faculty


def _curriculum_with_section(
    *,
    college: College,
    department: Department,
    short_name: str,
    course_number: str,
    semester: Semester,
    faculty: Faculty,
) -> tuple[Curriculum, Section]:
    """Create one curriculum, course, curriculum-course, and section."""
    CurriStatus._populate_attributes_and_db()
    curriculum = Curriculum.objects.create(
        college=college,
        short_name=short_name,
        long_name=f"{short_name} Program",
        status_id="approved",
        is_active=True,
    )
    course = Course.objects.create(
        department=department,
        number=course_number,
        title=f"{short_name} Course",
    )
    curriculum_course = CurriCrs.objects.create(
        curriculum=curriculum,
        course=course,
        level_number=1,
    )
    section = Section.objects.create(
        curriculum_course=curriculum_course,
        semester=semester,
        faculty=faculty,
        number=1,
    )
    return curriculum, section


def _registered_student(
    username: str,
    curriculum: Curriculum,
    section: Section,
    *,
    gender: str,
    semester: Semester,
) -> Student:
    """Create one student registered in a section and primary program."""
    user = User.objects.create_user(
        username,
        first_name=username.title(),
        last_name="Student",
    )
    student = Student(
        user=user,
        gender=gender,
        last_enrolled_semester=semester,
    )
    student.student_id = f"SID-{username.upper()}"
    student.primary_curriculum = curriculum
    student.save()
    Registration.objects.create(student=student, section=section)
    return student


def test_dean_dashboard_shows_program_stats_workloads_and_chair_selector(client):
    """Dean dashboard should show college enrollment and chair drilldown controls."""
    semester = _semester()
    second_semester = Semester.objects.create(
        academic_year=semester.academic_year,
        number=2,
        status_id="locked",
    )
    college = College.objects.create(code="DASHD", long_name="Dashboard Dean College")
    department = Department.objects.create(code="DDP", college=college)
    dean_user, _dean_faculty = _faculty_user("dean_dash", "Dean", college=college)
    _chair_user, chair_faculty = _faculty_user(
        "chair_dash",
        "Chair",
        college=college,
        department=department,
    )
    curriculum, section = _curriculum_with_section(
        college=college,
        department=department,
        short_name="DASH-ACCT",
        course_number="701",
        semester=semester,
        faculty=chair_faculty,
    )
    _registered_student("dash_female", curriculum, section, gender="f", semester=semester)
    _registered_student("dash_male", curriculum, section, gender="m", semester=semester)
    Curriculum.objects.create(
        college=college,
        short_name="DASH-ZERO",
        long_name="Zero Registration Program",
        status_id="approved",
        is_active=True,
    )
    Curriculum.objects.create(
        college=college,
        short_name="CBA-ACCT",
        long_name="Official Accounting Program",
        status_id="approved",
        is_active=True,
    )
    legacy_cur, legacy_sec = _curriculum_with_section(
        college=college,
        department=department,
        short_name="BBA - Accounting",
        course_number="704",
        semester=semester,
        faculty=chair_faculty,
    )
    legacy_cur.status_id = "pending"
    legacy_cur.is_active = False
    legacy_cur.save(update_fields=["status", "is_active"])
    _registered_student(
        "legacy_acct",
        legacy_cur,
        legacy_sec,
        gender="f",
        semester=semester,
    )
    raw_cur, raw_sec = _curriculum_with_section(
        college=college,
        department=department,
        short_name="DASH-RAW",
        course_number="702",
        semester=semester,
        faculty=chair_faculty,
    )
    raw_cur.status_id = "pending"
    raw_cur.is_active = False
    raw_cur.save(update_fields=["status", "is_active"])
    _registered_student("raw_dash", raw_cur, raw_sec, gender="f", semester=semester)
    future_year = AcademicYear.objects.create(start_date=date(2090, 9, 1))
    future_semester = Semester.objects.create(academic_year=future_year, number=2)
    future_curriculum, future_section = _curriculum_with_section(
        college=college,
        department=department,
        short_name="DASH-FUTURE",
        course_number="703",
        semester=future_semester,
        faculty=chair_faculty,
    )
    future_curriculum.is_active = False
    future_curriculum.save(update_fields=["is_active"])
    _registered_student(
        "future_dash",
        future_curriculum,
        future_section,
        gender="f",
        semester=future_semester,
    )

    client.force_login(dean_user)
    response = client.get(
        reverse("staff_role_dashboard", args=["dean"]),
        {"semester": str(future_semester.id), "chair_id": str(chair_faculty.id)},
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert "Dashboard term" in content
    assert "Student enrollment by program" in content
    assert "academic-program-chart" in content
    assert "academic-program-row--empty" in content
    assert "Freshman" in content
    assert "DASH-ACCT" in content
    assert "DASH-ZERO" in content
    assert "0 students" in content
    assert "CBA-ACCT" in content
    assert "BBA - Accounting" not in content
    assert "DASH-RAW" not in content
    assert "DASH-FUTURE" not in content
    assert "90-91" not in content
    assert "Semester 2" in content
    assert "2 students" in content
    assert "Faculty workload by program" in content
    assert "Schedule placement" in content
    assert chair_faculty.staff_profile.long_name in content

    sem2_response = client.get(
        reverse("staff_role_dashboard", args=["dean"]),
        {"semester": str(second_semester.id)},
    )
    sem2_content = sem2_response.content.decode()

    assert sem2_response.status_code == 200
    assert f'value="{second_semester.id}" selected' in sem2_content
    assert "90-91" not in sem2_content


def test_chair_dashboard_scopes_program_stats_to_chair_department(client):
    """Chair dashboard should use the chair department as the v1 responsibility scope."""
    semester = _semester()
    college = College.objects.create(code="DASHC", long_name="Dashboard Chair College")
    chair_department = Department.objects.create(code="CDP", college=college)
    other_department = Department.objects.create(code="ODP", college=college)
    chair_user, chair_faculty = _faculty_user(
        "chair_scope_dash",
        "Chair",
        college=college,
        department=chair_department,
    )
    visible_curriculum, visible_section = _curriculum_with_section(
        college=college,
        department=chair_department,
        short_name="CHAIR-VISIBLE",
        course_number="801",
        semester=semester,
        faculty=chair_faculty,
    )
    hidden_curriculum, hidden_section = _curriculum_with_section(
        college=college,
        department=other_department,
        short_name="CHAIR-HIDDEN",
        course_number="802",
        semester=semester,
        faculty=chair_faculty,
    )
    _registered_student(
        "chair_visible",
        visible_curriculum,
        visible_section,
        gender="f",
        semester=semester,
    )
    _registered_student(
        "chair_hidden",
        hidden_curriculum,
        hidden_section,
        gender="m",
        semester=semester,
    )

    client.force_login(chair_user)
    response = client.get(
        reverse("staff_role_dashboard", args=["chair"]),
        {"semester": str(semester.id)},
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert "CHAIR-VISIBLE" in content
    assert "CHAIR-HIDDEN" not in content
    assert semester.academic_year.code in content


def test_dean_curricula_orders_official_records_before_secondary_group(client):
    """Dean curriculum review should keep approved active programs first."""
    CurriStatus._populate_attributes_and_db()
    college = College.objects.create(code="DCLST", long_name="Dean Curriculum List")
    official = Curriculum.objects.create(
        college=college,
        short_name="OFFICIAL",
        long_name="Official Curriculum",
        status_id="approved",
        is_active=True,
    )
    pending = Curriculum.objects.create(
        college=college,
        short_name="RAW-PENDING",
        long_name="Raw Pending Curriculum",
        status_id="pending",
    )
    user, faculty = _faculty_user("dean_curri_list", "Dean", college=college)
    semester = _semester()
    department = Department.objects.create(code="DCLS", college=college)
    course = Course.objects.create(department=department, number="910", title="Counting")
    curriculum_course = CurriCrs.objects.create(curriculum=official, course=course)
    section = Section.objects.create(
        curriculum_course=curriculum_course,
        semester=semester,
        faculty=faculty,
    )
    _registered_student(
        "counting_student", official, section, gender="f", semester=semester
    )

    client.force_login(user)
    response = client.get(reverse("dean_curricula"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "<th>Students</th>" in content
    assert "<th>Courses</th>" in content
    assert content.index(official.short_name) < content.index("Inactive or pending")
    assert pending.short_name in content


def test_dean_curriculum_detail_groups_courses_and_shows_graph_action(
    client,
    settings,
    tmp_path,
):
    """Curriculum detail should group courses by level and expose graph action state."""
    settings.MEDIA_ROOT = tmp_path
    CurriStatus._populate_attributes_and_db()
    college = College.objects.create(code="DCDTL", long_name="Dean Curriculum Detail")
    department = Department.objects.create(code="DCD", college=college)
    curriculum = Curriculum.objects.create(
        college=college,
        short_name="DETAIL-CUR",
        long_name="Detail Curriculum",
        status_id="approved",
        is_active=True,
    )
    user, _faculty = _faculty_user("dean_curri_detail", "Dean", college=college)
    first_course = Course.objects.create(
        department=department,
        number="901",
        title="First Detail Course",
    )
    second_course = Course.objects.create(
        department=department,
        number="902",
        title="Second Detail Course",
    )
    CurriCrs.objects.create(curriculum=curriculum, course=first_course, level_number=1)
    CurriCrs.objects.create(curriculum=curriculum, course=second_course, level_number=2)

    client.force_login(user)
    response = client.get(reverse("dean_curriculum_detail", args=[curriculum.id]))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Total credits" in content
    assert "Level 1 (Year 1 Semester 1)" in content
    assert "Level 2 (Year 1 Semester 2)" in content
    assert "Export prerequisite graph from admin" not in content
    assert "No exported prerequisite graph is available." in content

    graph_dir = Path(settings.MEDIA_ROOT) / "Prereq"
    graph_dir.mkdir(parents=True)
    slug = slugify(curriculum.short_name, allow_unicode=False)
    (graph_dir / f"{slug}.json").write_text("{}", encoding="utf-8")
    graph_response = client.get(reverse("dean_curriculum_detail", args=[curriculum.id]))
    graph_content = graph_response.content.decode()
    graph_url = reverse("academics_prereq_graph", args=[slug])

    assert graph_response.status_code == 200
    assert f'src="{graph_url}"' in graph_content
    assert client.get(graph_url).status_code == 200
