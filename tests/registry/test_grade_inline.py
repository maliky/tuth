"""Tests for grade entry inline."""

import pytest

# from django.urls import reverse
from django.contrib import admin

from app.timetable.models.section import Section
from app.timetable.admin.section_registers import SecAdmin
from app.registry.admin.inlines import GradeIL


@pytest.mark.django_db
def test_sec_admin_has_grade_inline():
    """Check that the admin section shows the grades."""
    admin_obj = SecAdmin(Section, admin.site)
    assert GradeIL in admin_obj.inlines


# # Where is the admin_client coming from?
# @pytest.mark.django_db
# def test_grade_inline_visible(
#     admin_client,
#     curri_crs_factory,
#     sem_factory,
# ):

#     curriculum_course = curri_crs_factory()
#     semester = sem_factory()
#     section = Section.objects.create(
#         curriculum_course=curriculum_course,
#         semester=semester,
#         number=1,
#         start_date=semester.start_date,
#         end_date=semester.end_date,
#         max_seats=30,
#     )

#     url = reverse("admin:timetable_section_change", args=[section.pk])
#     response = admin_client.get(url)
#     assert response.status_code == 200
#     assert "grade_set" in response.content.decode()
