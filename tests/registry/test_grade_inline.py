"""Tests for grade entry inline."""

import pytest
from django.urls import reverse
from django.contrib import admin

from app.timetable.models.section import Section
from app.timetable.admin.registers.section import SectionAdmin
from app.registry.admin.inlines import GradeInline
from app.academics.models.program import Program
from app.academics.models.course import Course


@pytest.mark.django_db
def test_section_admin_has_grade_inline():
    admin_obj = SectionAdmin(Section, admin.site)
    assert GradeInline in admin_obj.inlines


@pytest.mark.django_db
def test_grade_inline_visible(admin_client, curriculum, semester):
    course = Course.get_unique_default()
    program = Program.objects.create(curriculum=curriculum, course=course)
    section = Section.objects.create(
        program=program,
        semester=semester,
        number=1,
        start_date=semester.start_date,
        end_date=semester.end_date,
        max_seats=30,
    )

    url = reverse("admin:timetable_section_change", args=[section.pk])
    response = admin_client.get(url)
    assert response.status_code == 200
    assert "grade_set" in response.content.decode()
