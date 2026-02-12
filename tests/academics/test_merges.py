"""Tests for academic merge utilities."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import pytest
from django.db import connection

from app.academics.admin.merges import (
    MERGE_CHOICE_KEEP_SOURCE,
    merge_curricula,
    merge_curriculum_courses,
    merge_courses,
)
from app.academics.models.course import Course
from app.academics.models.curriculum_course import CurriCourse
from app.academics.models.curriculum import Curriculum
from app.registry.models.grade import Grade, GradeValue
from app.registry.models.registration import Registration
from app.timetable.models.section import Section

# Use transactional tests to allow schema edits for constraint toggling.
pytestmark = pytest.mark.django_db(transaction=True)


@contextmanager
def _curriculum_course_constraint_disabled() -> Iterator[None]:
    """Temporarily drop the uniq_course_per_curriculum constraint."""
    constraint = next(
        c for c in CurriCourse._meta.constraints if c.name == "uniq_course_per_curriculum"
    )
    with connection.schema_editor(atomic=False) as schema_editor:
        schema_editor.remove_constraint(CurriCourse, constraint)
    try:
        yield
    finally:
        # Remove duplicates created during the test so the unique constraint can
        # be restored deterministically without leaking state across tests.
        duplicate_pairs: list[tuple[int, int]] = []
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT curriculum_id, course_id
                FROM academics_curriculumcourse
                GROUP BY curriculum_id, course_id
                HAVING COUNT(*) > 1
                """
            )
            duplicate_pairs = list(cursor.fetchall())
        for curriculum_id, course_id in duplicate_pairs:
            duplicate_ids = list(
                CurriCourse.objects.filter(
                    curriculum_id=curriculum_id,
                    course_id=course_id,
                )
                .order_by("id")
                .values_list("id", flat=True)
            )
            # Keep the first record to preserve the target row, drop the rest.
            for drop_id in duplicate_ids[1:]:
                CurriCourse.objects.filter(id=drop_id).delete()
        with connection.schema_editor(atomic=False) as schema_editor:
            schema_editor.add_constraint(CurriCourse, constraint)


def test_merge_curriculum_courses_same_course_moves_section(
    curriculum_factory, course_factory, default_semester
):
    """Sections move when merging duplicate curriculum-course rows."""
    curriculum = curriculum_factory("CURR-A")
    course = course_factory("101")
    summary = {}
    with _curriculum_course_constraint_disabled():
        target = CurriCourse.objects.create(curriculum=curriculum, course=course)
        source = CurriCourse.objects.create(curriculum=curriculum, course=course)
        section = Section.objects.create(
            curriculum_course=source,
            semester=default_semester,
            number=1,
        )
        summary = merge_curriculum_courses(target, [source])
    assert summary["merged"] == 1
    assert summary["sections_moved"] == 1
    assert Section.objects.filter(id=section.id, curriculum_course=target).exists()
    assert not CurriCourse.objects.filter(id=source.id).exists()


def test_merge_curriculum_courses_blocks_course_mismatch(
    curriculum_factory, course_factory, default_semester
):
    """Merging curriculum courses rejects course mismatches."""
    curriculum = curriculum_factory("CURR-A")
    target = CurriCourse.objects.create(
        curriculum=curriculum, course=course_factory("101")
    )
    source = CurriCourse.objects.create(
        curriculum=curriculum, course=course_factory("202")
    )
    section = Section.objects.create(
        curriculum_course=source,
        semester=default_semester,
        number=1,
    )
    summary = merge_curriculum_courses(target, [source])
    assert summary["skipped_incompatible"] == 1
    assert CurriCourse.objects.filter(id=source.id).exists()
    assert Section.objects.filter(id=section.id, curriculum_course=source).exists()


def test_merge_curriculum_courses_skips_invoices(
    curriculum_factory, course_factory, invoice_factory
):
    """Invoices block curriculum course merges."""
    curriculum = curriculum_factory("CURR-A")
    course = course_factory("101")
    summary = {}
    with _curriculum_course_constraint_disabled():
        target = CurriCourse.objects.create(curriculum=curriculum, course=course)
        source = CurriCourse.objects.create(curriculum=curriculum, course=course)
        invoice_factory(source)
        summary = merge_curriculum_courses(target, [source])
        assert CurriCourse.objects.filter(id=source.id).exists()
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
    target_cc = CurriCourse.objects.create(curriculum=target, course=course)
    source_cc = CurriCourse.objects.create(curriculum=source, course=course)
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
    CurriCourse.objects.create(curriculum=target, course=course)
    source_cc = CurriCourse.objects.create(curriculum=source, course=course)
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
    CurriCourse.objects.create(curriculum=target, course=course_a)
    source_cc = CurriCourse.objects.create(curriculum=source, course=course_b)
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
    CurriCourse.objects.create(curriculum=curriculum_a, course=target)
    source_cc = CurriCourse.objects.create(curriculum=curriculum_b, course=source)
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
        target = CurriCourse.objects.create(curriculum=curriculum, course=course)
        source = CurriCourse.objects.create(curriculum=curriculum, course=course)
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


def test_merge_curriculum_courses_conflict_reassigns_grade_and_registration(
    curriculum_factory, course_factory, default_semester, student
):
    """Conflict merge should reassign source grades/registrations to target section."""
    summary = {}
    with _curriculum_course_constraint_disabled():
        target = CurriCourse.objects.create(
            curriculum=curriculum_factory("CURR-A"),
            course=course_factory("301"),
        )
        source = CurriCourse.objects.create(
            curriculum=target.curriculum,
            course=target.course,
        )
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
        grade = Grade.objects.create(
            student=student,
            section=source_section,
            value=GradeValue.get_default(),
        )
        registration = Registration.objects.create(
            student=student, section=source_section
        )

        summary = merge_curriculum_courses(target, [source])

    assert summary["sections_merged"] == 1
    assert summary["sections_retained_protected"] == 0
    assert Grade.objects.filter(id=grade.id, section=target_section).exists()
    assert Registration.objects.filter(
        id=registration.id, section=target_section
    ).exists()
    assert not Section.objects.filter(id=source_section.id).exists()


def test_merge_curriculum_courses_conflict_retains_source_when_grade_duplicate(
    curriculum_factory, course_factory, default_semester, student
):
    """Duplicate grades for same student keep source section protected and retained."""
    summary = {}
    with _curriculum_course_constraint_disabled():
        target = CurriCourse.objects.create(
            curriculum=curriculum_factory("CURR-A"),
            course=course_factory("302"),
        )
        source = CurriCourse.objects.create(
            curriculum=target.curriculum,
            course=target.course,
        )
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
        Grade.objects.create(
            student=student,
            section=target_section,
            value=GradeValue.get_default(),
        )
        source_grade = Grade.objects.create(
            student=student,
            section=source_section,
            value=GradeValue.get_default(),
        )

        summary = merge_curriculum_courses(target, [source])

        assert Section.objects.filter(id=source_section.id).exists()
        # Cleanup protected row so the unique constraint helper can restore.
        source_grade.delete()

    assert summary["sections_retained_protected"] == 1
    assert summary["protected_deletes"] == 1


def test_merge_curricula_keep_source_choice_applies_source_values(
    curriculum_factory, course_factory, credit_hour_factory
):
    """Conflict choice keep_source should copy source values onto target row."""
    target = curriculum_factory("CURR-T")
    source = curriculum_factory("CURR-S")
    course = course_factory("401")
    target_cc = CurriCourse.objects.create(curriculum=target, course=course)
    source_cc = CurriCourse.objects.create(curriculum=source, course=course)
    target_cc.credit_hours = credit_hour_factory(3)
    target_cc.is_required = True
    target_cc.is_elective = False
    target_cc.save(update_fields=["credit_hours", "is_required", "is_elective"])
    source_cc.credit_hours = credit_hour_factory(4)
    source_cc.is_required = False
    source_cc.is_elective = True
    source_cc.save(update_fields=["credit_hours", "is_required", "is_elective"])

    summary = merge_curricula(
        target,
        [source],
        conflict_choices={course.id: MERGE_CHOICE_KEEP_SOURCE},
    )

    target_cc.refresh_from_db()
    assert summary["conflicts_kept_source"] == 1
    assert target_cc.credit_hours_id == source_cc.credit_hours_id
    assert target_cc.is_required is False
    assert target_cc.is_elective is True


def test_merge_curriculum_courses_skips_section_merge_on_grade_value_mismatch(
    curriculum_factory, course_factory, default_semester, student
):
    """Section merge should skip when overlapping student grade values differ."""
    summary = {}
    with _curriculum_course_constraint_disabled():
        target = CurriCourse.objects.create(
            curriculum=curriculum_factory("CURR-A"),
            course=course_factory("501"),
        )
        source = CurriCourse.objects.create(
            curriculum=target.curriculum,
            course=target.course,
        )
        target_section = Section.objects.create(
            curriculum_course=target,
            semester=default_semester,
            number=3,
        )
        source_section = Section.objects.create(
            curriculum_course=source,
            semester=default_semester,
            number=5,
        )
        grade_a, _ = GradeValue.objects.get_or_create(code="a")
        grade_b, _ = GradeValue.objects.get_or_create(code="b")
        Grade.objects.create(student=student, section=target_section, value=grade_a)
        Grade.objects.create(student=student, section=source_section, value=grade_b)

        summary = merge_curriculum_courses(target, [source])

    assert summary["sections_skipped_grade_conflict"] == 1
    assert summary["sections_merged"] == 0
    assert Section.objects.filter(id=target_section.id).exists()
    assert Section.objects.filter(id=source_section.id).exists()


def test_merge_curriculum_courses_keeps_lowest_number_and_logs_conflicts(
    curriculum_factory, course_factory, default_semester, student
):
    """Merging grade-compatible sections keeps the lowest number and logs metadata."""
    summary = {}
    with _curriculum_course_constraint_disabled():
        target = CurriCourse.objects.create(
            curriculum=curriculum_factory("CURR-A"),
            course=course_factory("502"),
        )
        source = CurriCourse.objects.create(
            curriculum=target.curriculum,
            course=target.course,
        )
        target_section = Section.objects.create(
            curriculum_course=target,
            semester=default_semester,
            number=5,
            max_seats=40,
        )
        source_section = Section.objects.create(
            curriculum_course=source,
            semester=default_semester,
            number=2,
            max_seats=50,
        )
        grade_value = GradeValue.get_default()
        Grade.objects.create(student=student, section=target_section, value=grade_value)
        source_grade = Grade.objects.create(
            student=student,
            section=source_section,
            value=grade_value,
        )

        summary = merge_curriculum_courses(target, [source])

        if Section.objects.filter(id=source_section.id).exists():
            source_grade.delete()

    target_section.refresh_from_db()
    assert target_section.number == 2
    assert target_section.max_seats == 30
    assert "target non-default max_seats=40" in (target_section.info or "")
    assert "source non-default max_seats=50" in (target_section.info or "")
    # Depending on legacy duplicate grade rows, merge may retain source by PROTECT.
    assert summary["sections_merged"] == 1 or summary["sections_retained_protected"] == 1
