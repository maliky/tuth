"""Tests for academic merge utilities."""

from __future__ import annotations

from contextlib import contextmanager

import pytest
from django.db import connection

from app.academics.admin.merges import (
    merge_curricula,
    merge_curriculum_courses,
    merge_courses,
)
from app.academics.models.course import Course
from app.academics.models.curriculum_course import CurriculumCourse
from app.academics.models.curriculum import Curriculum
from app.timetable.models.section import Section

# Use transactional tests to allow schema edits for constraint toggling.
pytestmark = pytest.mark.django_db(transaction=True)


@contextmanager
def _curriculum_course_constraint_disabled():
    """Temporarily drop the uniq_course_per_curriculum constraint."""
    constraint = next(
        c
        for c in CurriculumCourse._meta.constraints
        if c.name == "uniq_course_per_curriculum"
    )
    with connection.schema_editor(atomic=False) as schema_editor:
        schema_editor.remove_constraint(CurriculumCourse, constraint)
    try:
        yield
    finally:
        with connection.schema_editor(atomic=False) as schema_editor:
            schema_editor.add_constraint(CurriculumCourse, constraint)


def test_merge_curriculum_courses_same_course_moves_section(
    curriculum_factory, course_factory, default_semester
):
    """Sections move when merging duplicate curriculum-course rows."""
    curriculum = curriculum_factory("CURR-A")
    course = course_factory("101")
    summary = {}
    with _curriculum_course_constraint_disabled():
        target = CurriculumCourse.objects.create(curriculum=curriculum, course=course)
        source = CurriculumCourse.objects.create(curriculum=curriculum, course=course)
        section = Section.objects.create(
            curriculum_course=source,
            semester=default_semester,
            number=1,
        )
        summary = merge_curriculum_courses(target, [source])
    assert summary["merged"] == 1
    assert summary["sections_moved"] == 1
    assert Section.objects.filter(id=section.id, curriculum_course=target).exists()
    assert not CurriculumCourse.objects.filter(id=source.id).exists()


def test_merge_curriculum_courses_blocks_course_mismatch(
    curriculum_factory, course_factory, default_semester
):
    """Merging curriculum courses rejects course mismatches."""
    curriculum = curriculum_factory("CURR-A")
    target = CurriculumCourse.objects.create(
        curriculum=curriculum, course=course_factory("101")
    )
    source = CurriculumCourse.objects.create(
        curriculum=curriculum, course=course_factory("202")
    )
    section = Section.objects.create(
        curriculum_course=source,
        semester=default_semester,
        number=1,
    )
    summary = merge_curriculum_courses(target, [source])
    assert summary["skipped_incompatible"] == 1
    assert CurriculumCourse.objects.filter(id=source.id).exists()
    assert Section.objects.filter(id=section.id, curriculum_course=source).exists()


def test_merge_curriculum_courses_skips_invoices(
    curriculum_factory, course_factory, invoice_factory
):
    """Invoices block curriculum course merges."""
    curriculum = curriculum_factory("CURR-A")
    course = course_factory("101")
    summary = {}
    with _curriculum_course_constraint_disabled():
        target = CurriculumCourse.objects.create(curriculum=curriculum, course=course)
        source = CurriculumCourse.objects.create(curriculum=curriculum, course=course)
        invoice_factory(source)
        summary = merge_curriculum_courses(target, [source])
        assert CurriculumCourse.objects.filter(id=source.id).exists()
        # Cleanup so the unique constraint can be restored.
        source.delete()
        target.delete()
    assert summary["skipped_invoices"] == 1
    assert summary["merged"] == 0


def test_merge_curricula_overlapping_course_conflicts(
    curriculum_factory, course_factory, credit_hour_factory
):
    """Overlapping curriculum courses record conflicts without overwriting target."""
    target = curriculum_factory("CURR-T")
    source = curriculum_factory("CURR-S")
    course = course_factory("101")
    target_cc = CurriculumCourse.objects.create(curriculum=target, course=course)
    source_cc = CurriculumCourse.objects.create(curriculum=source, course=course)
    target_cc.credit_hours = credit_hour_factory(3)
    target_cc.is_required = True
    target_cc.is_elective = False
    target_cc.save(update_fields=["credit_hours", "is_required", "is_elective"])
    source_cc.credit_hours = credit_hour_factory(4)
    source_cc.is_required = False
    source_cc.is_elective = True
    source_cc.save(update_fields=["credit_hours", "is_required", "is_elective"])
    summary = merge_curricula(target, [source])
    assert summary["credit_hours_conflicts"] == 1
    assert summary["is_required_conflicts"] == 1
    assert summary["is_elective_conflicts"] == 1
    target_cc.refresh_from_db()
    assert target_cc.credit_hours_id == 3
    assert target_cc.is_required is True
    assert target_cc.is_elective is False


def test_merge_curricula_invoice_conflict_retains_source(
    curriculum_factory, course_factory, invoice_factory
):
    """Invoices prevent deleting the source curriculum when overlapping courses exist."""
    target = curriculum_factory("CURR-T")
    source = curriculum_factory("CURR-S")
    course = course_factory("101")
    CurriculumCourse.objects.create(curriculum=target, course=course)
    source_cc = CurriculumCourse.objects.create(curriculum=source, course=course)
    invoice_factory(source_cc)
    summary = merge_curricula(target, [source])
    assert summary["skipped_invoices"] == 1
    assert summary["curricula_retained"] == 1
    assert Curriculum.objects.filter(id=source.id).exists()


def test_merge_curricula_moves_curriculum_courses(curriculum_factory, course_factory):
    """Curriculum merges move non-overlapping curriculum courses."""
    target = curriculum_factory("CURR-T")
    source = curriculum_factory("CURR-S")
    course_a = course_factory("101")
    course_b = course_factory("202")
    CurriculumCourse.objects.create(curriculum=target, course=course_a)
    source_cc = CurriculumCourse.objects.create(curriculum=source, course=course_b)
    summary = merge_curricula(target, [source])
    assert summary["curriculum_courses_moved"] == 1
    assert summary["curricula_merged"] == 1
    source_cc.refresh_from_db()
    assert source_cc.curriculum_id == target.id
    assert not Curriculum.objects.filter(id=source.id).exists()


def test_merge_courses_moves_curriculum_courses(curriculum_factory, course_factory):
    """Course merges move curriculum-course links to the target."""
    curriculum_a = curriculum_factory("CURR-A")
    curriculum_b = curriculum_factory("CURR-B")
    target = course_factory("101")
    source = course_factory("202")
    CurriculumCourse.objects.create(curriculum=curriculum_a, course=target)
    source_cc = CurriculumCourse.objects.create(curriculum=curriculum_b, course=source)
    summary = merge_courses(target, [source])
    assert summary["curriculum_courses_moved"] == 1
    assert summary["merged"] == 1
    source_cc.refresh_from_db()
    assert source_cc.course_id == target.id
    assert not Course.objects.filter(id=source.id).exists()


def test_merge_curriculum_courses_merges_conflicting_sections(
    curriculum_factory, course_factory, default_semester
):
    """Conflicting sections merge and unique sections move to the target."""
    curriculum = curriculum_factory("CURR-A")
    course = course_factory("101")
    summary = {}
    with _curriculum_course_constraint_disabled():
        target = CurriculumCourse.objects.create(curriculum=curriculum, course=course)
        source = CurriculumCourse.objects.create(curriculum=curriculum, course=course)
        target_section = Section.objects.create(
            curriculum_course=target,
            semester=default_semester,
            number=1,
        )
        source_section = Section.objects.create(
            curriculum_course=source,
            semester=default_semester,
            number=1,
        )
        moved_section = Section.objects.create(
            curriculum_course=source,
            semester=default_semester,
            number=2,
        )
        summary = merge_curriculum_courses(target, [source])
    assert summary["sections_merged"] == 1
    assert summary["sections_moved"] == 1
    assert summary["merged"] == 1
    assert Section.objects.filter(id=target_section.id).exists()
    assert not Section.objects.filter(id=source_section.id).exists()
    assert Section.objects.filter(
        id=moved_section.id, curriculum_course_id=target.id
    ).exists()
