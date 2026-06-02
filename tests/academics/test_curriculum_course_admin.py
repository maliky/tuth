"""Focused tests for CurriCrs admin protected-delete behavior."""

from unittest.mock import patch

import pytest
from django.contrib import admin
from django.test import RequestFactory

from app.academics.admin.core import CurriCrsAdmin
from app.academics.models.curriculum_course import CurriCrs
from app.registry.models.grade import Grade, GradeValue
from app.timetable.models.section import Section


pytestmark = pytest.mark.django_db


def _request_with_user(superuser):
    """Return an admin-like request carrying the acting user."""
    request = RequestFactory().post("/admin/academics/curriculumcourse/")
    request.user = superuser
    return request


def test_curriculum_course_delete_shows_protected_msg(
    curriculum_course, semester, student, superuser
):
    """Deleting a programmed course with grade-linked sections should be blocked."""
    section = Section.objects.create(
        curriculum_course=curriculum_course,
        semester=semester,
        number=99,
    )
    Grade.objects.create(student=student, section=section, value=GradeValue.get_dft())
    admin_obj = CurriCrsAdmin(CurriCrs, admin.site)
    request = _request_with_user(superuser)

    with patch.object(admin_obj, "message_user") as message_user:
        admin_obj.delete_model(request, curriculum_course)

    assert CurriCrs.objects.filter(id=curriculum_course.id).exists()
    assert message_user.call_count == 1
    assert "Cannot delete programmed course" in str(message_user.call_args.args[1])
