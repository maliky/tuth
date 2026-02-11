"""Test the admin app for finance."""

from unittest.mock import patch

import pytest
from django.contrib import admin
from django.test import RequestFactory

from app.registry.models.grade import Grade, GradeValue
from app.timetable.models.section import Section
from app.timetable.models.session import SecSession
from app.timetable.models.schedule import Schedule
from app.timetable.admin.section_registers import SectionAdmin


@pytest.mark.django_db
def test_section_admin_list_display_fields():
    """Check the required field are there."""
    admin_obj = SectionAdmin(Section, admin.site)
    assert "space_codes" in admin_obj.list_display
    assert "session_count" in admin_obj.list_display
    assert "credit_hours" in admin_obj.list_display


@pytest.mark.django_db
def test_section_admin_counts(section, room, schedule):
    """Check that the admin does update the number of registration."""
    other = Schedule.get_default(day=2)
    SecSession.objects.create(section=section, room=room, schedule=schedule)
    SecSession.objects.create(section=section, room=room, schedule=other)
    admin_obj = SectionAdmin(Section, admin.site)
    assert admin_obj.session_count(section) == f"{section.number}/2"
    assert admin_obj.credit_hours(section) == section.curriculum_course.credit_hours_id


def _request_with_user(superuser):
    """Return an admin-like request carrying the acting user."""
    request = RequestFactory().post("/admin/timetable/section/")
    request.user = superuser
    return request


@pytest.mark.django_db
def test_section_admin_delete_model_shows_protected_message(section, student, superuser):
    """Deleting a section with grades should show a clear protected message."""
    Grade.objects.create(student=student, section=section, value=GradeValue.get_default())
    admin_obj = SectionAdmin(Section, admin.site)
    request = _request_with_user(superuser)

    with patch.object(admin_obj, "message_user") as message_user:
        admin_obj.delete_model(request, section)

    assert Section.objects.filter(id=section.id).exists()
    assert message_user.call_count == 1
    assert "Cannot delete section because grades depend on it" in str(
        message_user.call_args.args[1]
    )


@pytest.mark.django_db
def test_section_admin_bulk_delete_shows_protected_message(section, student, superuser):
    """Bulk section delete should stop and show the protected guidance."""
    Grade.objects.create(student=student, section=section, value=GradeValue.get_default())
    admin_obj = SectionAdmin(Section, admin.site)
    request = _request_with_user(superuser)

    with patch.object(admin_obj, "message_user") as message_user:
        admin_obj.delete_queryset(request, Section.objects.filter(id=section.id))

    assert Section.objects.filter(id=section.id).exists()
    assert message_user.call_count == 1
    assert "Bulk delete stopped: some sections have grades attached" in str(
        message_user.call_args.args[1]
    )
