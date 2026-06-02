"""Test the admin app for finance."""

from unittest.mock import patch

import pytest
from django.contrib import admin
from django.test import RequestFactory

from app.registry.models.grade import Grade, GradeValue
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
