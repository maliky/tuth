"""Test the admin app for finance."""

from unittest.mock import patch

import pytest
from django.contrib import admin
from django.contrib.auth.models import Permission, User
from django.test import RequestFactory

from app.academics.models import College, Course, CurriCrs, Curriculum, Department
from app.registry.models.grade import Grade, GradeValue
from app.registry.models.credit_hours import CreditHour
from app.shared.auth.perms import UserRole
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester, SemesterStatus
from app.timetable.models.session import SecSession
from app.timetable.models.schedule import Schedule
from app.timetable.admin.section_registers import SecAdmin


@pytest.mark.django_db
def test_sec_admin_list_display_fields():
    """Check the required field are there."""
    admin_obj = SecAdmin(Section, admin.site)
    assert "space_codes" in admin_obj.list_display
    assert "session_count" in admin_obj.list_display
    assert "credit_hours" in admin_obj.list_display


@pytest.mark.django_db
def test_sec_admin_counts(section, room, schedule):
    """Check that the admin does update the number of registration."""
    other = Schedule.get_dft(day=2)
    SecSession.objects.create(section=section, room=room, schedule=schedule)
    SecSession.objects.create(section=section, room=room, schedule=other)
    admin_obj = SecAdmin(Section, admin.site)
    assert admin_obj.session_count(section) == f"{section.number}/2"
    assert admin_obj.credit_hours(section) == section.curriculum_course.credit_hours_id


def _request_with_user(superuser):
    """Return an admin-like request carrying the acting user."""
    request = RequestFactory().post("/admin/timetable/section/")
    request.user = superuser
    return request


def _section_admin_request(user: User, query: dict[str, str] | None = None):
    """Return a section changelist request for queryset checks."""
    request = RequestFactory().get("/admin/timetable/section/", data=query or {})
    request.user = user
    return request


def _section_perm(codename: str) -> Permission:
    """Return a timetable section permission."""
    return Permission.objects.get(
        codename=codename,
        content_type__app_label="timetable",
        content_type__model="section",
    )


def _registrar_user(username: str, role: UserRole) -> User:
    """Create a registrar-like staff user with section view permission."""
    user = User.objects.create_user(username=username, is_staff=True)
    group = role.value.group
    group.permissions.add(_section_perm("view_section"))
    user.groups.add(group)
    return user


@pytest.mark.django_db
def test_sec_admin_delete_model_shows_protected_msg(section, student, superuser):
    """Deleting a section with grades should show a clear protected message."""
    Grade.objects.create(student=student, section=section, value=GradeValue.get_dft())
    admin_obj = SecAdmin(Section, admin.site)
    request = _request_with_user(superuser)

    with patch.object(admin_obj, "message_user") as message_user:
        admin_obj.delete_model(request, section)

    assert Section.objects.filter(id=section.id).exists()
    assert message_user.call_count == 1
    assert "Cannot delete section because grades depend on it" in str(
        message_user.call_args.args[1]
    )


@pytest.mark.django_db
def test_sec_admin_bulk_delete_shows_protected_msg(section, student, superuser):
    """Bulk section delete should stop and show the protected guidance."""
    Grade.objects.create(student=student, section=section, value=GradeValue.get_dft())
    admin_obj = SecAdmin(Section, admin.site)
    request = _request_with_user(superuser)

    with patch.object(admin_obj, "message_user") as message_user:
        admin_obj.delete_queryset(request, Section.objects.filter(id=section.id))

    assert Section.objects.filter(id=section.id).exists()
    assert message_user.call_count == 1
    assert "Bulk delete stopped: some sections have grades attached" in str(
        message_user.call_args.args[1]
    )


@pytest.mark.django_db
def test_sec_admin_initial_semester_prefers_registration_open_semester(
    academic_year_factory,
):
    """Section add form should prefill semester with registration-open semester."""
    SemesterStatus._populate_attributes_and_db()
    academic_year = academic_year_factory()
    open_semester = Semester.objects.create(
        academic_year=academic_year,
        number=1,
        status_id="registration",
    )
    Semester.objects.create(
        academic_year=academic_year,
        number=2,
        status_id="planning",
    )
    admin_obj = SecAdmin(Section, admin.site)
    request = RequestFactory().get("/admin/timetable/section/add/")

    initial = admin_obj.get_changeform_initial_data(request)

    assert initial["semester"] == str(open_semester.pk)


@pytest.mark.django_db
def test_sec_admin_initial_semester_falls_back_to_current_semester(semester):
    """Section add form should fallback to current semester when none is open."""
    SemesterStatus._populate_attributes_and_db()
    semester.status_id = "planning"
    semester.save(update_fields=["status"])
    admin_obj = SecAdmin(Section, admin.site)
    request = RequestFactory().get("/admin/timetable/section/add/")

    with (
        patch.object(Semester, "regio_open_sem", return_value=(None, None)),
        patch.object(Semester, "get_current_sem", return_value=semester),
    ):
        initial = admin_obj.get_changeform_initial_data(request)

    assert initial["semester"] == str(semester.pk)


@pytest.mark.django_db
def test_sec_admin_superuser_sees_all_sections(section, sec_factory, superuser):
    """Superusers should bypass faculty scoping in section admin."""
    other_section = sec_factory("887", "CURRI_SECTION_ADMIN_SUPER", 1, 1)
    admin_obj = SecAdmin(Section, admin.site)
    request = _section_admin_request(superuser)

    section_ids = set(admin_obj.get_queryset(request).values_list("id", flat=True))

    assert {section.id, other_section.id}.issubset(section_ids)


@pytest.mark.django_db
def test_sec_admin_registrar_officer_sees_all_sections(section, sec_factory):
    """Registrar officers with section permission should see all sections."""
    other_section = sec_factory("888", "CURRI_SECTION_ADMIN_REG_OFFICER", 1, 1)
    user = _registrar_user("section_admin_reg_officer", UserRole.REGISTRAR_OFFICER)
    admin_obj = SecAdmin(Section, admin.site)
    request = _section_admin_request(user)

    section_ids = set(admin_obj.get_queryset(request).values_list("id", flat=True))

    assert {section.id, other_section.id}.issubset(section_ids)


@pytest.mark.django_db
def test_sec_admin_registrar_sees_all_sections(section, sec_factory):
    """Registrars with section permission should see all sections."""
    other_section = sec_factory("889", "CURRI_SECTION_ADMIN_REGISTRAR", 1, 1)
    user = _registrar_user("section_admin_registrar", UserRole.REGISTRAR)
    admin_obj = SecAdmin(Section, admin.site)
    request = _section_admin_request(user)

    section_ids = set(admin_obj.get_queryset(request).values_list("id", flat=True))

    assert {section.id, other_section.id}.issubset(section_ids)


@pytest.mark.django_db
def test_sec_admin_registrar_faculty_dual_role_bypasses_college_scope(
    section,
    faculty,
    semester,
):
    """Registrar users with a Faculty profile should still see all sections."""
    other_college = College.objects.create(
        code="CBA", long_name="College of Business Administration"
    )
    department = Department.objects.create(code="ACCT", college=other_college)
    course = Course.objects.create(
        department=department,
        number="901",
        title="Registrar Scope Accounting",
    )
    curriculum = Curriculum.objects.create(
        short_name="CBA-REG-SCOPE",
        college=other_college,
        long_name="Registrar Scope Program",
    )
    curriculum_course = CurriCrs.objects.create(
        curriculum=curriculum,
        course=course,
        credit_hours=CreditHour.objects.get(code=3),
    )
    other_section = Section.objects.create(
        curriculum_course=curriculum_course,
        semester=semester,
        number=1,
    )
    user = faculty.staff_profile.user
    user.is_staff = True
    group = UserRole.REGISTRAR_OFFICER.value.group
    group.permissions.add(_section_perm("view_section"))
    user.groups.add(group)
    user.save(update_fields=["is_staff"])
    admin_obj = SecAdmin(Section, admin.site)
    request = _section_admin_request(user)

    section_ids = set(admin_obj.get_queryset(request).values_list("id", flat=True))

    assert {section.id, other_section.id}.issubset(section_ids)


@pytest.mark.django_db
def test_sec_admin_faculty_user_sees_only_owned_sections(
    section,
    sec_factory,
    faculty,
    faculty_factory,
):
    """Faculty users should keep the existing own-section restriction."""
    other_faculty = faculty_factory("section_admin_other_faculty")
    section.faculty = faculty
    section.save(update_fields=["faculty"])
    other_section = sec_factory("890", "CURRI_SECTION_ADMIN_FACULTY", 1, 1)
    other_section.faculty = other_faculty
    other_section.save(update_fields=["faculty"])
    user = faculty.staff_profile.user
    user.is_staff = True
    user.user_permissions.add(_section_perm("view_section"))
    user.save(update_fields=["is_staff"])
    admin_obj = SecAdmin(Section, admin.site)
    request = _section_admin_request(user)

    section_ids = set(admin_obj.get_queryset(request).values_list("id", flat=True))

    assert section.id in section_ids
    assert other_section.id not in section_ids


@pytest.mark.django_db
def test_sec_admin_non_registrar_non_faculty_staff_sees_no_sections(section):
    """Section permission alone should not bypass faculty scoping for staff."""
    user = User.objects.create_user(username="section_admin_staff", is_staff=True)
    user.user_permissions.add(_section_perm("view_section"))
    admin_obj = SecAdmin(Section, admin.site)
    request = _section_admin_request(user)

    assert admin_obj.get_queryset(request).count() == 0


@pytest.mark.django_db
def test_sec_admin_registration_lookup_remains_open_semester_scoped(
    academic_year_factory,
    curriculum_course_factory,
    superuser,
):
    """Registration section autocomplete should still only expose open sections."""
    SemesterStatus._populate_attributes_and_db()
    academic_year = academic_year_factory()
    open_semester = Semester.objects.create(
        academic_year=academic_year,
        number=1,
        status_id="registration",
    )
    closed_semester = Semester.objects.create(
        academic_year=academic_year,
        number=2,
        status_id="planning",
    )
    open_section = Section.objects.create(
        semester=open_semester,
        curriculum_course=curriculum_course_factory(
            "891",
            "CURRI_SECTION_ADMIN_LOOKUP",
        ),
        number=1,
    )
    closed_section = Section.objects.create(
        semester=closed_semester,
        curriculum_course=curriculum_course_factory(
            "892",
            "CURRI_SECTION_ADMIN_LOOKUP",
        ),
        number=1,
    )
    admin_obj = SecAdmin(Section, admin.site)
    request = _section_admin_request(
        superuser,
        {
            "app_label": "registry",
            "model_name": "registration",
            "field_name": "section",
        },
    )

    section_ids = set(admin_obj.get_queryset(request).values_list("id", flat=True))

    assert open_section.id in section_ids
    assert closed_section.id not in section_ids
