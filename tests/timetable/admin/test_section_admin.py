"""Test the admin app for finance."""

import pytest
from django.contrib import admin

from app.timetable.models.section import Section
from app.timetable.models.session import SecSession
from app.timetable.models.schedule import Schedule
from app.timetable.admin.registers.section import SectionAdmin


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
    assert admin_obj.session_count(section) == 2
    assert admin_obj.credit_hours(section) == section.program.credit_hours
