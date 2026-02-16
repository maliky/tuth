"""Tests for the course admin bulk department update action."""

from __future__ import annotations

from typing import TypeAlias

import pytest
from django.contrib import messages
from django.http import HttpResponse
from django.test import RequestFactory

from app.academics.admin.actions import update_department
from app.academics.models.college import College
from app.academics.models.course import Course
from app.academics.models.curriculum_course import CurriCourse
from app.academics.models.department import Department

pytestmark = pytest.mark.django_db


MessageT: TypeAlias = tuple[str, int]


class DummyAdmin:
    """Simple admin stub that captures action feedback messages."""

    def __init__(self) -> None:
        self.messages: list[MessageT] = []

    def message_user(self, request, message, level=messages.INFO) -> None:
        """Store user-facing action messages for assertions."""
        self.messages.append((str(message), int(level)))


def _post_update_dpt(
    *,
    selected_course_ids: list[int],
    department_id: int,
    queryset,
) -> tuple[HttpResponse, DummyAdmin]:
    """Run the bulk update action and return the response + admin stub."""
    request = RequestFactory().post(
        "/admin/academics/course/",
        data={
            "apply": "yes",
            "_selected_action": [str(course_id) for course_id in selected_course_ids],
            "dept": str(department_id),
        },
    )
    model_admin = DummyAdmin()
    response = update_department(model_admin, request, queryset)
    return response, model_admin


def test_update_department_moves_course_when_no_collision() -> None:
    """Bulk action should move a course directly when target has no collision."""
    college = College.get_default()
    source_dept = Department.objects.create(code="SRC", college=college)
    target_dept = Department.objects.create(code="TGT", college=college)
    source_course = Course.objects.create(
        department=source_dept,
        number="101",
        title="Source course",
    )

    queryset = Course.objects.filter(pk=source_course.pk)
    response, model_admin = _post_update_dpt(
        selected_course_ids=[source_course.pk],
        department_id=target_dept.pk,
        queryset=queryset,
    )

    assert response.status_code == 302
    source_course.refresh_from_db()
    assert source_course.department_id == target_dept.pk
    assert source_course.short_code == f"{target_dept.code}{source_course.number}"
    assert any(
        "Moved 1 course(s)" in msg and str(target_dept) in msg
        for msg, _ in model_admin.messages
    )


def test_update_department_merges_collision_with_existing_course(
    curriculum_factory,
) -> None:
    """Bulk action should merge into existing target-department course on collision."""
    college = College.get_default()
    source_dept = Department.objects.create(code="SRC2", college=college)
    target_dept = Department.objects.create(code="TGT2", college=college)
    target_course = Course.objects.create(
        department=target_dept,
        number="201",
        title="Target course",
    )
    source_course = Course.objects.create(
        department=source_dept,
        number="201",
        title="Source course",
    )
    CurriCourse.objects.create(
        curriculum=curriculum_factory("CURRI-TGT"),
        course=target_course,
    )
    source_curriculum_course = CurriCourse.objects.create(
        curriculum=curriculum_factory("CURRI-SRC"),
        course=source_course,
    )

    queryset = Course.objects.filter(pk=source_course.pk)
    response, model_admin = _post_update_dpt(
        selected_course_ids=[source_course.pk],
        department_id=target_dept.pk,
        queryset=queryset,
    )

    assert response.status_code == 302
    assert not Course.objects.filter(pk=source_course.pk).exists()
    source_curriculum_course.refresh_from_db()
    assert source_curriculum_course.course_id == target_course.pk
    assert any("Merged 1 colliding course(s)" in msg for msg, _ in model_admin.messages)


def test_update_department_skips_collision_merge_when_invoice_exists(
    curriculum_factory,
    invoice_factory,
) -> None:
    """Invoices on source curriculum courses should block collision merges."""
    college = College.get_default()
    source_dept = Department.objects.create(code="SRC3", college=college)
    target_dept = Department.objects.create(code="TGT3", college=college)
    target_course = Course.objects.create(
        department=target_dept,
        number="301",
        title="Target course",
    )
    source_course = Course.objects.create(
        department=source_dept,
        number="301",
        title="Source course",
    )
    curriculum = curriculum_factory("CURRI-INV")
    CurriCourse.objects.create(curriculum=curriculum, course=target_course)
    source_curriculum_course = CurriCourse.objects.create(
        curriculum=curriculum,
        course=source_course,
    )
    invoice_factory(source_curriculum_course)

    queryset = Course.objects.filter(pk=source_course.pk)
    response, model_admin = _post_update_dpt(
        selected_course_ids=[source_course.pk],
        department_id=target_dept.pk,
        queryset=queryset,
    )

    assert response.status_code == 302
    source_course.refresh_from_db()
    assert source_course.department_id == source_dept.pk
    assert any("Skipped 1 collision merge(s)" in msg for msg, _ in model_admin.messages)
