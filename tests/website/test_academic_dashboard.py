"""Academic dashboard coverage for dean and chair workspaces."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse
from django.utils.text import slugify

from app.academics.choices import AcademicCareer
from app.academics.models.college import College
from app.academics.models.course import Course
from app.academics.models.curriculum import CurriStatus, Curriculum
from app.academics.models.curriculum_course import CurriCrs
from app.academics.models.department import Department
from app.people.models.faculty import Faculty, FacultyWorkloadSnapshot
from app.people.models.role_assignment import RoleAssignment
from app.people.models.staffs import Staff
from app.people.models.student import Student
from app.registry.models.registration import Registration
from app.shared.auth.perms import UserRole
from app.spaces.models.core import Room, Space
from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester, SemesterStatus
from app.timetable.models.session import SecSession
from app.timetable.models.schedule import Schedule
from app.website.services.academic_dashboard_programs import program_stack_chart

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


def _sidebar_href(response, label: str) -> str:
    """Return one sidebar link href from a rendered staff page."""
    return next(
        str(link["href"])
        for link in response.context["sidebar_links"]
        if link["label"] == label
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


def _placed_session(section: Section, *, room_code: str = "101") -> SecSession:
    """Attach one complete room/time placement to a section."""
    space = Space.objects.create(code=f"SP{section.id}", full_name="Schedule Space")
    room = Room.objects.create(code=room_code, space=space)
    schedule = Schedule.objects.create(
        weekday=1,
        start_time="09:00",
        end_time="10:15",
    )
    return SecSession.objects.create(section=section, room=room, schedule=schedule)


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
    section.current_registrations = 2
    section.max_seats = 20
    section.save(update_fields=["current_registrations", "max_seats"])
    placed_session = _placed_session(section)
    FacultyWorkloadSnapshot.objects.create(
        faculty=chair_faculty,
        semester=semester,
        credit_hours_assigned=12,
        credit_hours_delivered=15,
        overload_flag=True,
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
        {
            "academic_career": "all",
            "semester": str(future_semester.id),
            "chair_id": str(chair_faculty.id),
        },
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
    assert "1 overload" in content
    assert str(placed_session.room) in content
    assert "09:00-10:15" in content
    assert "2/20" in content
    assert chair_faculty.staff_profile.long_name in content

    sem2_response = client.get(
        reverse("staff_role_dashboard", args=["dean"]),
        {"academic_career": "all", "semester": str(second_semester.id)},
    )
    sem2_content = sem2_response.content.decode()

    assert sem2_response.status_code == 200
    assert f'value="{second_semester.id}" selected' in sem2_content
    assert "90-91" not in sem2_content


def test_program_stack_chart_uses_graduate_level_labels_for_graduate_programs():
    """Graduate-only dashboard charts should use graduate level buckets."""
    semester = _semester()
    college = College.objects.create(code="GDASH", long_name="Graduate Dashboard")
    department = Department.objects.create(code="GDB", college=college)
    _faculty_user_account, faculty = _faculty_user(
        "graduate_chart_faculty",
        "Faculty",
        college=college,
        department=department,
    )
    curriculum, section = _curriculum_with_section(
        college=college,
        department=department,
        short_name="GRAD-MBAM",
        course_number="701",
        semester=semester,
        faculty=faculty,
    )
    curriculum.academic_career = AcademicCareer.GRADUATE
    curriculum.save(update_fields=["academic_career"])
    student = _registered_student(
        "grad_chart",
        curriculum,
        section,
        gender="f",
        semester=semester,
    )
    student.academic_career = AcademicCareer.GRADUATE
    student.save(update_fields=["academic_career"])

    chart = program_stack_chart(Curriculum.objects.filter(pk=curriculum.pk), semester)
    legend = cast(list[dict[str, Any]], chart["legend"])
    rows = cast(list[dict[str, Any]], chart["rows"])
    segments = cast(list[dict[str, Any]], rows[0]["segments"])

    assert [row["label"] for row in legend] == ["Graduate 1", "Graduate 2"]
    assert segments[0]["label"] == "G1 1"


def test_program_stack_chart_labels_mixed_career_legends() -> None:
    """All-career charts should not label graduate buckets as undergraduate."""
    semester = _semester()
    college = College.objects.create(code="MXD", long_name="Mixed Dashboard")
    department = Department.objects.create(code="MXD", college=college)
    _faculty_account, faculty = _faculty_user(
        "mixed_chart_faculty",
        "Faculty",
        college=college,
        department=department,
    )
    undergraduate_curriculum, undergraduate_section = _curriculum_with_section(
        college=college,
        department=department,
        short_name="UG-MIX",
        course_number="711",
        semester=semester,
        faculty=faculty,
    )
    graduate_curriculum, graduate_section = _curriculum_with_section(
        college=college,
        department=department,
        short_name="GRAD-MIX",
        course_number="712",
        semester=semester,
        faculty=faculty,
    )
    graduate_curriculum.academic_career = AcademicCareer.GRADUATE
    graduate_curriculum.save(update_fields=["academic_career"])
    undergraduate_student = _registered_student(
        "mixed_ug",
        undergraduate_curriculum,
        undergraduate_section,
        gender="m",
        semester=semester,
    )
    graduate_student = _registered_student(
        "mixed_grad",
        graduate_curriculum,
        graduate_section,
        gender="f",
        semester=semester,
    )
    graduate_student.academic_career = AcademicCareer.GRADUATE
    graduate_student.save(update_fields=["academic_career"])

    chart = program_stack_chart(Curriculum.objects.filter(college=college), semester)
    legend = cast(list[dict[str, Any]], chart["legend"])
    rows = cast(list[dict[str, Any]], chart["rows"])

    assert undergraduate_student.academic_career == AcademicCareer.UNDERGRADUATE
    assert [row["label"] for row in legend] == [
        "UG Freshman",
        "UG Sophomore",
        "UG Junior",
        "UG Senior",
        "Graduate 1",
        "Graduate 2",
    ]
    assert any(
        segment["label"] == "G1 1"
        for row in rows
        for segment in cast(list[dict[str, Any]], row["segments"])
    )


def test_dean_dashboard_defaults_to_graduate_career(client):
    """Academic dashboards should default to graduate programs."""
    semester = _semester()
    college = College.objects.create(code="GDEF", long_name="Graduate Default College")
    department = Department.objects.create(code="GDD", college=college)
    dean_user, _dean_faculty = _faculty_user(
        "dean_grad_default",
        "Dean",
        college=college,
    )
    _faculty_user_account, faculty = _faculty_user(
        "grad_default_faculty",
        "Faculty",
        college=college,
        department=department,
    )
    graduate_curriculum, graduate_section = _curriculum_with_section(
        college=college,
        department=department,
        short_name="GRAD-DEFAULT",
        course_number="731",
        semester=semester,
        faculty=faculty,
    )
    graduate_curriculum.academic_career = AcademicCareer.GRADUATE
    graduate_curriculum.save(update_fields=["academic_career"])
    undergraduate_curriculum, undergraduate_section = _curriculum_with_section(
        college=college,
        department=department,
        short_name="UG-DEFAULT",
        course_number="732",
        semester=semester,
        faculty=faculty,
    )
    _registered_student(
        "grad_default",
        graduate_curriculum,
        graduate_section,
        gender="f",
        semester=semester,
    )
    _registered_student(
        "ug_default",
        undergraduate_curriculum,
        undergraduate_section,
        gender="m",
        semester=semester,
    )

    client.force_login(dean_user)
    response = client.get(reverse("staff_role_dashboard", args=["dean"]))
    content = response.content.decode()

    assert response.status_code == 200
    assert "GRAD-DEFAULT" in content
    assert "UG-DEFAULT" not in content
    assert 'name="academic_career"' in content
    assert 'value="graduate" selected' in content
    assert "portal-theme-graduate" in content

    all_response = client.get(
        reverse("staff_role_dashboard", args=["dean"]),
        {"academic_career": "all"},
    )

    assert all_response.status_code == 200
    assert "portal-theme-graduate" not in all_response.content.decode()
    assert _sidebar_href(all_response, "Curriculum review") == (
        f"{reverse('dean_curricula')}?academic_career=all"
    )
    assert _sidebar_href(all_response, "Grade rosters") == (
        f"{reverse('staff_grade_rosters', args=['dean'])}?academic_career=all"
    )
    assert _sidebar_href(all_response, "Grade transcripts") == (
        f"{reverse('staff_grade_transcripts', args=['dean'])}?academic_career=all"
    )

    undergrad_response = client.get(
        reverse("staff_role_dashboard", args=["dean"]),
        {"academic_career": "undergraduate"},
    )

    assert undergrad_response.status_code == 200
    assert _sidebar_href(undergrad_response, "Curriculum review") == (
        f"{reverse('dean_curricula')}?academic_career=undergraduate"
    )


def test_faculty_dashboard_preserves_career_scope_in_sidebar(client):
    """Faculty dashboard task links should keep the selected career query."""
    semester = _semester()
    college = College.objects.create(code="FCAR", long_name="Faculty Career College")
    department = Department.objects.create(code="FCR", college=college)
    faculty_user, faculty = _faculty_user(
        "faculty_career_sidebar",
        "Faculty",
        college=college,
        department=department,
    )
    _curriculum, _section = _curriculum_with_section(
        college=college,
        department=department,
        short_name="FAC-SCOPE",
        course_number="733",
        semester=semester,
        faculty=faculty,
    )

    client.force_login(faculty_user)
    response = client.get(
        reverse("staff_role_dashboard", args=["faculty"]),
        {"academic_career": "all"},
    )
    actions = response.context["actions"]

    assert response.status_code == 200
    assert _sidebar_href(response, "Dashboard") == (
        f"{reverse('staff_role_dashboard', args=['faculty'])}?academic_career=all"
    )
    assert _sidebar_href(response, "Grade tasks") == (
        f"{reverse('faculty_grade_sections')}?academic_career=all"
    )
    assert all(action["label"] != "Open grade entry" for action in actions)


def test_dean_dashboard_schedule_coverage_lists_all_sections_and_tba(client):
    """Schedule coverage should include every scoped section, not only ten rows."""
    semester = _semester()
    college = College.objects.create(code="DSCH", long_name="Schedule College")
    department = Department.objects.create(code="DSC", college=college)
    dean_user, _dean_faculty = _faculty_user("dean_schedule", "Dean", college=college)
    _faculty_account, faculty = _faculty_user(
        "schedule_faculty",
        "Faculty",
        college=college,
        department=department,
    )
    curriculum = Curriculum.objects.create(
        college=college,
        short_name="SCHED-CUR",
        long_name="Schedule Curriculum",
        status_id="approved",
        is_active=True,
    )
    course = Course.objects.create(
        department=department,
        number="730",
        title="Schedule Coverage",
    )
    curriculum_course = CurriCrs.objects.create(
        curriculum=curriculum,
        course=course,
        level_number=1,
    )
    first_section = Section.objects.create(
        curriculum_course=curriculum_course,
        semester=semester,
        faculty=faculty,
        number=1,
    )
    placed_session = _placed_session(first_section, room_code="210")
    for number in range(2, 13):
        Section.objects.create(
            curriculum_course=curriculum_course,
            semester=semester,
            faculty=faculty,
            number=number,
        )

    client.force_login(dean_user)
    response = client.get(
        reverse("staff_role_dashboard", args=["dean"]),
        {"academic_career": "all"},
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert "Schedule placement" in content
    assert str(placed_session.room) in content
    assert "Sec 12" in content
    assert ">12<" in content
    assert ">1<" in content
    assert ">11<" in content
    assert "TBA" in content


def test_dean_dashboard_prefers_role_assignment_college(client):
    """Dean dashboard should use active dean role scope before profile fallback."""
    semester = _semester()
    profile_college = College.objects.create(code="DPROF", long_name="Profile College")
    assigned_college = College.objects.create(
        code="DROLE",
        long_name="Assigned Dean College",
    )
    profile_department = Department.objects.create(code="DPF", college=profile_college)
    assigned_department = Department.objects.create(
        code="DRA",
        college=assigned_college,
    )
    dean_user, _dean_faculty = _faculty_user(
        "dean_role_scope",
        "Dean",
        college=profile_college,
    )
    _chair_user, chair_faculty = _faculty_user(
        "dean_role_chair",
        "Chair",
        college=assigned_college,
        department=assigned_department,
    )
    RoleAssignment.objects.create(
        user=dean_user,
        group=UserRole.DEAN.value.group,
        college=assigned_college,
        start_date=date.today(),
    )
    visible_curriculum, visible_section = _curriculum_with_section(
        college=assigned_college,
        department=assigned_department,
        short_name="DEAN-ROLE",
        course_number="711",
        semester=semester,
        faculty=chair_faculty,
    )
    hidden_curriculum, hidden_section = _curriculum_with_section(
        college=profile_college,
        department=profile_department,
        short_name="DEAN-PROFILE",
        course_number="712",
        semester=semester,
        faculty=chair_faculty,
    )
    _registered_student(
        "dr_visible",
        visible_curriculum,
        visible_section,
        gender="f",
        semester=semester,
    )
    _registered_student(
        "dr_hidden",
        hidden_curriculum,
        hidden_section,
        gender="m",
        semester=semester,
    )

    client.force_login(dean_user)
    response = client.get(
        reverse("staff_role_dashboard", args=["dean"]),
        {"academic_career": "all"},
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert "Assigned Dean College" in content
    assert "DEAN-ROLE" in content
    assert "DEAN-PROFILE" not in content


def test_vpaa_dashboard_prompts_for_dean_before_chart(client):
    """VPAA dashboard should not show dean data until one dean role is selected."""
    _semester()
    college = College.objects.create(code="VPSEL", long_name="VPAA Select College")
    dean_user, _dean_faculty = _faculty_user("vpaa_select_dean", "Dean", college=college)
    RoleAssignment.objects.create(
        user=dean_user,
        group=UserRole.DEAN.value.group,
        college=college,
        start_date=date.today(),
    )
    vpaa_user = User.objects.create_user("vpaa_prompt", password="PassW0rd!")
    _group_user(vpaa_user, "VPAA")

    client.force_login(vpaa_user)
    response = client.get(reverse("staff_role_dashboard", args=["vpaa"]))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Dean overview" in content
    assert "Select dean/college" in content
    assert "VPSEL -" in content
    assert "Vpaa Select Dean" in content
    assert "academic-program-chart" not in content
    assert 'id="academic-chair"' not in content


def test_vpaa_dashboard_selected_dean_role_scopes_to_college(client):
    """VPAA selected dean overview should show one dean college only."""
    semester = _semester()
    visible_college = College.objects.create(code="VPVIS", long_name="Visible College")
    hidden_college = College.objects.create(code="VPHID", long_name="Hidden College")
    visible_department = Department.objects.create(code="VPV", college=visible_college)
    hidden_department = Department.objects.create(code="VPH", college=hidden_college)
    visible_dean, _visible_dean_faculty = _faculty_user(
        "vpaa_visible_dean",
        "Dean",
        college=visible_college,
    )
    hidden_dean, _hidden_dean_faculty = _faculty_user(
        "vpaa_hidden_dean",
        "Dean",
        college=hidden_college,
    )
    visible_role = RoleAssignment.objects.create(
        user=visible_dean,
        group=UserRole.DEAN.value.group,
        college=visible_college,
        start_date=date.today(),
    )
    RoleAssignment.objects.create(
        user=hidden_dean,
        group=UserRole.DEAN.value.group,
        college=hidden_college,
        start_date=date.today(),
    )
    _hidden_faculty_user, hidden_faculty = _faculty_user(
        "vpaa_hidden_faculty",
        "Faculty",
        college=hidden_college,
        department=hidden_department,
    )
    _visible_faculty_user, visible_faculty = _faculty_user(
        "vpaa_chart_faculty",
        "Faculty",
        college=visible_college,
        department=visible_department,
    )
    visible_curriculum, visible_section = _curriculum_with_section(
        college=visible_college,
        department=visible_department,
        short_name="VPAA-VISIBLE",
        course_number="721",
        semester=semester,
        faculty=visible_faculty,
    )
    hidden_curriculum, hidden_section = _curriculum_with_section(
        college=hidden_college,
        department=hidden_department,
        short_name="VPAA-HIDDEN",
        course_number="722",
        semester=semester,
        faculty=hidden_faculty,
    )
    _registered_student(
        "vpaa_visible",
        visible_curriculum,
        visible_section,
        gender="f",
        semester=semester,
    )
    _registered_student(
        "vpaa_hidden",
        hidden_curriculum,
        hidden_section,
        gender="m",
        semester=semester,
    )
    vpaa_user = User.objects.create_user("vpaa_selected", password="PassW0rd!")
    _group_user(vpaa_user, "VPAA")

    client.force_login(vpaa_user)
    response = client.get(
        reverse("staff_role_dashboard", args=["vpaa"]),
        {
            "academic_career": "all",
            "dean_role_id": str(visible_role.id),
            "semester": str(semester.id),
        },
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert "Visible College" in content
    assert "VPAA-VISIBLE" in content
    assert "VPAA-HIDDEN" not in content
    assert "Faculty workload by program" in content
    assert "Schedule placement" in content
    assert "Sections" in content
    assert "TBA" in content
    assert 'id="academic-chair"' not in content


def test_vpaa_dashboard_dean_selector_uses_faculty_college_fallback(client):
    """VPAA should see dean group users even before scoped roles are backfilled."""
    semester = _semester()
    college = College.objects.create(code="VPFB", long_name="VPAA Fallback College")
    department = Department.objects.create(code="VPF", college=college)
    _dean_user, dean_faculty = _faculty_user(
        "vpaa_fallback_dean",
        "Dean",
        college=college,
    )
    _faculty_account, faculty = _faculty_user(
        "vpaa_fallback_faculty",
        "Faculty",
        college=college,
        department=department,
    )
    curriculum, section = _curriculum_with_section(
        college=college,
        department=department,
        short_name="VPAA-FALLBACK",
        course_number="723",
        semester=semester,
        faculty=faculty,
    )
    _registered_student(
        "vpaa_fb",
        curriculum,
        section,
        gender="f",
        semester=semester,
    )
    vpaa_user = User.objects.create_user("vpaa_fallback", password="PassW0rd!")
    _group_user(vpaa_user, "VPAA")

    client.force_login(vpaa_user)
    response = client.get(
        reverse("staff_role_dashboard", args=["vpaa"]),
        {
            "academic_career": "all",
            "dean_role_id": f"faculty:{dean_faculty.id}",
            "semester": str(semester.id),
        },
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert f'value="faculty:{dean_faculty.id}" selected' in content
    assert "VPAA Fallback College" in content
    assert "VPAA-FALLBACK" in content
    assert 'id="academic-chair"' not in content


def test_vpaa_dean_selector_exposes_one_active_dean_per_college(client):
    """VPAA dean selector should collapse duplicate active dean roles by college."""
    _semester()
    college = College.objects.create(code="VPDUP", long_name="VPAA Duplicate College")
    older_dean, _older_faculty = _faculty_user(
        "vpaa_older_dean",
        "Dean",
        college=college,
    )
    newer_dean, _newer_faculty = _faculty_user(
        "vpaa_newer_dean",
        "Dean",
        college=college,
    )
    RoleAssignment.objects.create(
        user=older_dean,
        group=UserRole.DEAN.value.group,
        college=college,
        start_date=date.today() - timedelta(days=7),
    )
    newer_role = RoleAssignment.objects.create(
        user=newer_dean,
        group=UserRole.DEAN.value.group,
        college=college,
        start_date=date.today(),
    )
    vpaa_user = User.objects.create_user("vpaa_dup", password="PassW0rd!")
    _group_user(vpaa_user, "VPAA")

    client.force_login(vpaa_user)
    response = client.get(reverse("staff_role_dashboard", args=["vpaa"]))
    content = response.content.decode()

    assert response.status_code == 200
    assert content.count("VPDUP -") == 1
    assert f'value="{newer_role.id}"' in content
    assert "Vpaa Newer Dean" in content
    assert "Vpaa Older Dean" not in content


def test_dean_dashboard_chair_selector_uses_department_scope(client):
    """Dean chair selector should include chairs scoped by department college."""
    semester = _semester()
    dean_college = College.objects.create(code="DCHF", long_name="Dean Chair Fallback")
    other_college = College.objects.create(code="OCHF", long_name="Other College")
    department = Department.objects.create(code="DCF", college=dean_college)
    dean_user, _dean_faculty = _faculty_user(
        "dean_chair_fallback",
        "Dean",
        college=dean_college,
    )
    _chair_user, chair_faculty = _faculty_user(
        "chair_department_scope",
        "Chair",
        college=other_college,
        department=department,
    )
    curriculum, section = _curriculum_with_section(
        college=dean_college,
        department=department,
        short_name="CHAIR-DEPT",
        course_number="724",
        semester=semester,
        faculty=chair_faculty,
    )
    _registered_student(
        "chair_dept",
        curriculum,
        section,
        gender="m",
        semester=semester,
    )

    client.force_login(dean_user)
    response = client.get(
        reverse("staff_role_dashboard", args=["dean"]),
        {
            "academic_career": "all",
            "chair_id": str(chair_faculty.id),
            "semester": str(semester.id),
        },
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert f'value="{chair_faculty.id}" selected' in content
    assert chair_faculty.staff_profile.long_name in content
    assert "CHAIR-DEPT" in content


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
        {"academic_career": "all", "semester": str(semester.id)},
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
    response = client.get(reverse("dean_curricula"), {"academic_career": "all"})
    content = response.content.decode()

    assert response.status_code == 200
    assert "<th>Students</th>" in content
    assert "<th>Courses</th>" in content
    assert content.index(official.short_name) < content.index("Inactive or pending")
    assert pending.short_name in content
    assert _sidebar_href(response, "Dashboard") == (
        f"{reverse('staff_role_dashboard', args=['dean'])}?academic_career=all"
    )
    assert _sidebar_href(response, "Grade rosters") == (
        f"{reverse('staff_grade_rosters', args=['dean'])}?academic_career=all"
    )


def test_dean_curriculum_detail_groups_courses_and_shows_graph_action(
    client,
    monkeypatch,
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
    assert "Generate prerequisite graph" in content
    assert "No exported prerequisite graph is available." in content

    slug = slugify(curriculum.short_name, allow_unicode=False)

    def fake_export_graph(target: Curriculum) -> None:
        """Write the JSON marker used by the graph viewer."""
        graph_dir = Path(settings.MEDIA_ROOT) / "Prereq"
        graph_dir.mkdir(parents=True)
        graph_slug = slugify(target.short_name, allow_unicode=False)
        (graph_dir / f"{graph_slug}.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        "app.website.services.dean_portal.export_prereq_graph",
        fake_export_graph,
    )
    graph_response = client.post(
        reverse("dean_curriculum_export_prereq_graph", args=[curriculum.id]),
        follow=True,
    )
    graph_content = graph_response.content.decode()
    graph_url = reverse("academics_prereq_graph", args=[slug])

    assert graph_response.status_code == 200
    assert "Regenerate prerequisite graph" in graph_content
    assert f'src="{graph_url}"' in graph_content
    assert f'href="{graph_url}"' in graph_content
    assert "Open graph" in graph_content
    graph_view = client.get(graph_url)
    assert graph_view.status_code == 200
    assert graph_view.headers["X-Frame-Options"] == "SAMEORIGIN"
