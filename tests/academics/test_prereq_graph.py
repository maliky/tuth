"""Tests for prerequisite graph exports."""

from __future__ import annotations

import json

import pytest
from django.test.utils import override_settings

from app.academics import prereq_graph
from app.academics.models.course import Course
from app.academics.models.curriculum_course import CurriCourse
from app.academics.models.prerequisite import Prerequisite
from app.academics.models.requirement_group import (
    CurriCourseReqGp,
    CurriCourseReqMember,
    ReqKind,
)


pytestmark = [pytest.mark.django_db]


def test_export_prereq_graph_includes_global_prereqs(
    tmp_path, curri_factory, monkeypatch
):
    """Global prerequisites should be included for curriculum courses."""
    curriculum = curri_factory("BSC_ECON_TEST_GRAPH")
    course = Course.get_unique_dft()
    prereq_course = Course.get_unique_dft()
    other_course = Course.get_unique_dft()
    CurriCourse.objects.create(curriculum=curriculum, course=course)
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

    prereq_label = prereq_graph._crs_display(prereq_course)

    assert any(
        link.get("source") == f"C{prereq_course.id}"
        and link.get("target") == f"C{course.id}"
        for link in links
    )
    assert not any(link.get("target") == f"C{other_course.id}" for link in links)

    dot_text = output.dot_path.read_text(encoding="utf-8")
    assert prereq_label in dot_text


def test_export_prereq_graph_coreq_clusters_and_alt_clusters(
    tmp_path, curri_factory, monkeypatch
):
    """Coreq edges should route via cluster boundaries while alt edges stay direct."""
    curriculum = curri_factory("BSC_COREQ_ALT_GRAPH")
    course_anchor = Course.get_unique_dft()
    course_coreq_a = Course.get_unique_dft()
    course_coreq_b = Course.get_unique_dft()
    course_alt_a = Course.get_unique_dft()
    course_alt_b = Course.get_unique_dft()

    cc_anchor = CurriCourse.objects.create(
        curriculum=curriculum,
        course=course_anchor,
        level_number=1,
    )
    cc_coreq_a = CurriCourse.objects.create(
        curriculum=curriculum,
        course=course_coreq_a,
        level_number=2,
    )
    cc_coreq_b = CurriCourse.objects.create(
        curriculum=curriculum,
        course=course_coreq_b,
        level_number=2,
    )
    cc_alt_a = CurriCourse.objects.create(
        curriculum=curriculum,
        course=course_alt_a,
        level_number=2,
        required_group_number=7,
    )
    CurriCourse.objects.create(
        curriculum=curriculum,
        course=course_alt_b,
        level_number=2,
        required_group_number=7,
    )

    # Incoming edge into coreq cluster and outgoing edge from the same cluster.
    Prerequisite.objects.create(
        curriculum=curriculum,
        course=cc_coreq_a.course,
        prerequisite_course=cc_anchor.course,
    )
    Prerequisite.objects.create(
        curriculum=curriculum,
        course=cc_anchor.course,
        prerequisite_course=cc_coreq_a.course,
    )
    # Edge into alternate cluster member should stay as a normal node edge.
    Prerequisite.objects.create(
        curriculum=curriculum,
        course=cc_alt_a.course,
        prerequisite_course=cc_anchor.course,
    )

    coreq_group = CurriCourseReqGp.objects.create(
        curriculum_course=cc_coreq_a,
        kind=ReqKind.COREQ_ALL,
        label="Coreq Bundle",
    )
    CurriCourseReqMember.objects.create(
        group=coreq_group,
        required_course=cc_coreq_b.course,
    )

    monkeypatch.setattr(prereq_graph, "_render_png", lambda *args, **kwargs: None)
    with override_settings(MEDIA_ROOT=tmp_path):
        output = prereq_graph.export_prereq_graph(curriculum)

    payload = json.loads(output.json_path.read_text(encoding="utf-8"))
    coreq_groups = payload.get("coreq_groups", [])
    assert any(group.get("group_id") == coreq_group.id for group in coreq_groups)

    dot_text = output.dot_path.read_text(encoding="utf-8")
    coreq_cluster_name = f"cluster_COREQ{coreq_group.id}"
    assert f"subgraph {coreq_cluster_name}" in dot_text
    assert (
        f'C{course_anchor.id} -> C{course_coreq_a.id} [lhead="{coreq_cluster_name}"];'
        in dot_text
    )
    assert (
        f'C{course_coreq_a.id} -> C{course_anchor.id} [ltail="{coreq_cluster_name}"];'
        in dot_text
    )
    assert "subgraph cluster_ALT7" in dot_text
    assert f"C{course_anchor.id} -> C{course_alt_a.id};" in dot_text
