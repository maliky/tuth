"""Tests for prerequisite graph exports."""

from __future__ import annotations

import json

import pytest
from django.test.utils import override_settings

from app.academics import prereq_graph
from app.academics.models.course import Course
from app.academics.models.curriculum_course import CurriculumCourse
from app.academics.models.prerequisite import Prerequisite


pytestmark = [pytest.mark.django_db]


def test_export_prereq_graph_includes_global_prereqs(
    tmp_path, curriculum_factory, monkeypatch
):
    """Global prerequisites should be included for curriculum courses."""
    curriculum = curriculum_factory("BSC_ECON_TEST_GRAPH")
    course = Course.get_unique_default()
    prereq_course = Course.get_unique_default()
    other_course = Course.get_unique_default()
    CurriculumCourse.objects.create(curriculum=curriculum, course=course)
    Prerequisite.objects.create(
        course=course, prerequisite_course=prereq_course, curriculum=None
    )
    Prerequisite.objects.create(
        course=other_course, prerequisite_course=prereq_course, curriculum=None
    )

    monkeypatch.setattr(prereq_graph, "_render_png", lambda *args, **kwargs: None)
    with override_settings(MEDIA_ROOT=tmp_path):
        output = prereq_graph.export_prereq_graph(curriculum)

    payload = json.loads(output.json_path.read_text(encoding="utf-8"))
    links = payload.get("links", [])

    prereq_label = prereq_graph._course_display(prereq_course)

    assert any(
        link.get("source") == f"C{prereq_course.id}"
        and link.get("target") == f"C{course.id}"
        for link in links
    )
    assert not any(link.get("target") == f"C{other_course.id}" for link in links)

    dot_text = output.dot_path.read_text(encoding="utf-8")
    assert prereq_label in dot_text
