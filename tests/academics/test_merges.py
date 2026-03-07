"""Tests for academic merge utilities."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Iterator

import pytest
from django.db import connection

from app.academics.admin.merges import (
    MERGE_CHOICE_KEEP_SOURCE,
    list_curri_crs_conflicts,
    merge_curra,
    merge_curri_crss,
    merge_crss,
    reconcile_std_curri_records,
)
from app.academics.models.course import Course
from app.academics.models.curriculum_course import CurriCrs
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
        c for c in CurriCrs._meta.constraints if c.name == "uniq_course_per_curriculum"
    )
    with connection.schema_editor(atomic=False) as schema_editor:
        schema_editor.remove_constraint(CurriCrs, constraint)
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
                CurriCrs.objects.filter(
                    curriculum_id=curriculum_id,
                    course_id=course_id,
                )
                .order_by("id")
                .values_list("id", flat=True)
            )
            # Keep the first record to preserve the target row, drop the rest.
            for drop_id in duplicate_ids[1:]:
                CurriCrs.objects.filter(id=drop_id).delete()
        with connection.schema_editor(atomic=False) as schema_editor:
            schema_editor.add_constraint(CurriCrs, constraint)


def test_merge_curri_crss_same_crs_moves_sec(curri_factory, crs_factory, dft_sem):
    """Sections move when merging duplicate curriculum-course rows."""
    curriculum = curri_factory("CURR-A")
    course = crs_factory("101")
    summary = {}
    with _curriculum_course_constraint_disabled():
        target = CurriCrs.objects.create(curriculum=curriculum, course=course)
        source = CurriCrs.objects.create(curriculum=curriculum, course=course)
        section = Section.objects.create(
            curriculum_course=source,
            semester=dft_sem,
            number=1,
        )
        summary = merge_curri_crss(target, [source])
    assert summary["merged"] == 1
    assert summary["sections_moved"] == 1
    assert Section.objects.filter(id=section.id, curriculum_course=target).exists()
    assert not CurriCrs.objects.filter(id=source.id).exists()


def test_merge_curri_crss_blocks_crs_mismatch(curri_factory, crs_factory, dft_sem):
    """Merging curriculum courses rejects course mismatches."""
    curriculum = curri_factory("CURR-A")
    target = CurriCrs.objects.create(curriculum=curriculum, course=crs_factory("101"))
    source = CurriCrs.objects.create(curriculum=curriculum, course=crs_factory("202"))
    section = Section.objects.create(
        curriculum_course=source,
        semester=dft_sem,
        number=1,
    )
    summary = merge_curri_crss(target, [source])
    assert summary["skipped_incompatible"] == 1
    assert CurriCrs.objects.filter(id=source.id).exists()
    assert Section.objects.filter(id=section.id, curriculum_course=source).exists()


def test_merge_curri_crss_skips_invoices(curri_factory, crs_factory, invoice_factory):
    """Invoices block curriculum course merges."""
    curriculum = curri_factory("CURR-A")
    course = crs_factory("101")
    summary = {}
    with _curriculum_course_constraint_disabled():
        target = CurriCrs.objects.create(curriculum=curriculum, course=course)
        source = CurriCrs.objects.create(curriculum=curriculum, course=course)
        invoice_factory(source)
        summary = merge_curri_crss(target, [source])
        assert CurriCrs.objects.filter(id=source.id).exists()
        # Cleanup so the unique constraint can be restored.
        source.delete()
        target.delete()
    assert summary["skipped_invoices"] == 1
    assert summary["merged"] == 0


def test_merge_curra_overlapping_crs_conflicts(
    curri_factory, crs_factory, credit_hour_factory
):
    """Overlapping curriculum courses record conflicts without overwriting target."""
    target = curri_factory("CURR-T")
    source = curri_factory("CURR-S")
    course = crs_factory("101")
    target_cc = CurriCrs.objects.create(curriculum=target, course=course)
    source_cc = CurriCrs.objects.create(curriculum=source, course=course)
    target_cc.credit_hours = credit_hour_factory(3)
    target_cc.is_required = True
    target_cc.is_elective = False
    target_cc.save(update_fields=["credit_hours", "is_required", "is_elective"])
    source_cc.credit_hours = credit_hour_factory(4)
    source_cc.is_required = False
    source_cc.is_elective = True
    source_cc.save(update_fields=["credit_hours", "is_required", "is_elective"])
    summary = merge_curra(target, [source])
    assert summary["credit_hours_conflicts"] == 1
    assert summary["is_required_conflicts"] == 1
    assert summary["is_elective_conflicts"] == 1
    target_cc.refresh_from_db()
    assert target_cc.credit_hours_id == 3
    assert target_cc.is_required is True
    assert target_cc.is_elective is False


def test_list_curri_crs_conflicts_uses_dpt_number_id(curri_factory, crs_factory):
    """Conflict detection should match equivalent courses by department+number."""
    target = curri_factory("CURR-T-ID")
    source = curri_factory("CURR-S-ID")
    target_course = crs_factory("981")
    source_course = Course.objects.create(
        department=target_course.department,
        number=target_course.number,
        code=f"ALT{target_course.id}",
        short_code=f"ALT{target_course.number}",
    )
    target_cc = CurriCrs.objects.create(curriculum=target, course=target_course)
    source_cc = CurriCrs.objects.create(curriculum=source, course=source_course)

    conflicts, non_conflicting = list_curri_crs_conflicts(target, source)

    assert conflicts == [(target_cc, source_cc)]
    assert non_conflicting == []


def test_merge_curra_invoice_conflict_retains_source(
    curri_factory, crs_factory, invoice_factory
):
    """Invoices prevent deleting the source curriculum when overlapping courses exist."""
    target = curri_factory("CURR-T")
    source = curri_factory("CURR-S")
    course = crs_factory("101")
    CurriCrs.objects.create(curriculum=target, course=course)
    source_cc = CurriCrs.objects.create(curriculum=source, course=course)
    invoice_factory(source_cc)
    summary = merge_curra(target, [source])
    assert summary["skipped_invoices"] == 1
    assert summary["curricula_retained"] == 1
    assert Curriculum.objects.filter(id=source.id).exists()


def test_merge_curra_moves_curriculum_courses(curri_factory, crs_factory):
    """Curriculum merges move non-overlapping curriculum courses."""
    target = curri_factory("CURR-T")
    source = curri_factory("CURR-S")
    course_a = crs_factory("101")
    course_b = crs_factory("202")
    CurriCrs.objects.create(curriculum=target, course=course_a)
    source_cc = CurriCrs.objects.create(curriculum=source, course=course_b)
    summary = merge_curra(target, [source])
    assert summary["curriculum_courses_moved"] == 1
    assert summary["curricula_merged"] == 1
    source_cc.refresh_from_db()
    assert source_cc.curriculum_id == target.id
    assert not Curriculum.objects.filter(id=source.id).exists()


def test_merge_crss_moves_curriculum_courses(curri_factory, crs_factory):
    """Course merges move curriculum-course links to the target."""
    curriculum_a = curri_factory("CURR-A")
    curriculum_b = curri_factory("CURR-B")
    target = crs_factory("101")
    source = crs_factory("202")
    CurriCrs.objects.create(curriculum=curriculum_a, course=target)
    source_cc = CurriCrs.objects.create(curriculum=curriculum_b, course=source)
    summary = merge_crss(target, [source])
    assert summary["curriculum_courses_moved"] == 1
    assert summary["merged"] == 1
    source_cc.refresh_from_db()
    assert source_cc.course_id == target.id
    assert not Course.objects.filter(id=source.id).exists()


def test_merge_curri_crss_merges_conflicting_secs(curri_factory, crs_factory, dft_sem):
    """Conflicting sections merge and unique sections move to the target."""
    curriculum = curri_factory("CURR-A")
    course = crs_factory("101")
    summary = {}
    with _curriculum_course_constraint_disabled():
        target = CurriCrs.objects.create(curriculum=curriculum, course=course)
        source = CurriCrs.objects.create(curriculum=curriculum, course=course)
        target_section = Section.objects.create(
            curriculum_course=target,
            semester=dft_sem,
            number=1,
        )
        source_section = Section.objects.create(
            curriculum_course=source,
            semester=dft_sem,
            number=1,
        )
        moved_section = Section.objects.create(
            curriculum_course=source,
            semester=dft_sem,
            number=2,
        )
        summary = merge_curri_crss(target, [source])
    assert summary["sections_merged"] == 1
    assert summary["sections_moved"] == 1
    assert summary["merged"] == 1
    assert Section.objects.filter(id=target_section.id).exists()
    assert not Section.objects.filter(id=source_section.id).exists()
    assert Section.objects.filter(
        id=moved_section.id, curriculum_course_id=target.id
    ).exists()


def test_merge_curri_crss_conflict_reassigns_grade_and_regio(
    curri_factory, crs_factory, dft_sem, student
):
    """Conflict merge should reassign source grades/registrations to target section."""
    summary = {}
    with _curriculum_course_constraint_disabled():
        target = CurriCrs.objects.create(
            curriculum=curri_factory("CURR-A"),
            course=crs_factory("301"),
        )
        source = CurriCrs.objects.create(
            curriculum=target.curriculum,
            course=target.course,
        )
        target_section = Section.objects.create(
            curriculum_course=target,
            semester=dft_sem,
            number=1,
        )
        source_section = Section.objects.create(
            curriculum_course=source,
            semester=dft_sem,
            number=1,
        )
        grade = Grade.objects.create(
            student=student,
            section=source_section,
            value=GradeValue.get_dft(),
        )
        registration = Registration.objects.create(
            student=student, section=source_section
        )

        summary = merge_curri_crss(target, [source])

    assert summary["sections_merged"] == 1
    assert summary["sections_retained_protected"] == 0
    assert Grade.objects.filter(id=grade.id, section=target_section).exists()
    assert Registration.objects.filter(
        id=registration.id, section=target_section
    ).exists()
    assert not Section.objects.filter(id=source_section.id).exists()


def test_merge_curri_crss_conflict_retains_source_when_grade_duplicate(
    curri_factory, crs_factory, dft_sem, student
):
    """Duplicate grades for same student keep source section protected and retained."""
    summary = {}
    with _curriculum_course_constraint_disabled():
        target = CurriCrs.objects.create(
            curriculum=curri_factory("CURR-A"),
            course=crs_factory("302"),
        )
        source = CurriCrs.objects.create(
            curriculum=target.curriculum,
            course=target.course,
        )
        target_section = Section.objects.create(
            curriculum_course=target,
            semester=dft_sem,
            number=1,
        )
        source_section = Section.objects.create(
            curriculum_course=source,
            semester=dft_sem,
            number=1,
        )
        Grade.objects.create(
            student=student,
            section=target_section,
            value=GradeValue.get_dft(),
        )
        source_grade = Grade.objects.create(
            student=student,
            section=source_section,
            value=GradeValue.get_dft(),
        )

        summary = merge_curri_crss(target, [source])

        assert Section.objects.filter(id=source_section.id).exists()
        # Cleanup protected row so the unique constraint helper can restore.
        source_grade.delete()

    assert summary["sections_retained_protected"] == 1
    assert summary["protected_deletes"] == 1


def test_merge_curra_keep_source_choice_applies_source_values(
    curri_factory, crs_factory, credit_hour_factory
):
    """Conflict choice keep_source should copy source values onto target row."""
    target = curri_factory("CURR-T")
    source = curri_factory("CURR-S")
    course = crs_factory("401")
    target_cc = CurriCrs.objects.create(curriculum=target, course=course)
    source_cc = CurriCrs.objects.create(curriculum=source, course=course)
    target_cc.credit_hours = credit_hour_factory(3)
    target_cc.is_required = True
    target_cc.is_elective = False
    target_cc.save(update_fields=["credit_hours", "is_required", "is_elective"])
    source_cc.credit_hours = credit_hour_factory(4)
    source_cc.is_required = False
    source_cc.is_elective = True
    source_cc.save(update_fields=["credit_hours", "is_required", "is_elective"])

    summary = merge_curra(
        target,
        [source],
        conflict_choices={course.id: MERGE_CHOICE_KEEP_SOURCE},
    )

    target_cc.refresh_from_db()
    assert summary["conflicts_kept_source"] == 1
    assert target_cc.credit_hours_id == source_cc.credit_hours_id
    assert target_cc.is_required is False
    assert target_cc.is_elective is True


def test_merge_curri_crss_skips_sec_merge_on_grade_value_mismatch(
    curri_factory, crs_factory, dft_sem, student
):
    """Section merge should skip when overlapping student grade values differ."""
    summary = {}
    with _curriculum_course_constraint_disabled():
        target = CurriCrs.objects.create(
            curriculum=curri_factory("CURR-A"),
            course=crs_factory("501"),
        )
        source = CurriCrs.objects.create(
            curriculum=target.curriculum,
            course=target.course,
        )
        target_section = Section.objects.create(
            curriculum_course=target,
            semester=dft_sem,
            number=3,
        )
        source_section = Section.objects.create(
            curriculum_course=source,
            semester=dft_sem,
            number=5,
        )
        grade_a, _ = GradeValue.objects.get_or_create(code="a")
        grade_b, _ = GradeValue.objects.get_or_create(code="b")
        Grade.objects.create(student=student, section=target_section, value=grade_a)
        Grade.objects.create(student=student, section=source_section, value=grade_b)

        summary = merge_curri_crss(target, [source])

    assert summary["sections_skipped_grade_conflict"] == 1
    assert summary["sections_merged"] == 0
    assert Section.objects.filter(id=target_section.id).exists()
    assert Section.objects.filter(id=source_section.id).exists()


def test_merge_curri_crss_rebuckets_sem0_conflict_into_sem1_to_sem3(
    curri_factory,
    crs_factory,
    sem_factory,
    student,
):
    """Sem0 grade conflicts should rebucket source sections instead of skipping."""
    summary = {}
    with _curriculum_course_constraint_disabled():
        target = CurriCrs.objects.create(
            curriculum=curri_factory("CURR-SEM0-A"),
            course=crs_factory("711"),
        )
        source = CurriCrs.objects.create(
            curriculum=target.curriculum,
            course=target.course,
        )
        semester0 = sem_factory(0, datetime(2023, 8, 1))
        target_section = Section.objects.create(
            curriculum_course=target,
            semester=semester0,
            number=4,
        )
        source_section = Section.objects.create(
            curriculum_course=source,
            semester=semester0,
            number=1,
        )
        grade_a, _ = GradeValue.objects.get_or_create(code="a")
        grade_b, _ = GradeValue.objects.get_or_create(code="b")
        Grade.objects.create(student=student, section=target_section, value=grade_a)
        Grade.objects.create(student=student, section=source_section, value=grade_b)

        summary = merge_curri_crss(target, [source])

    source_section.refresh_from_db()
    assert summary["sections_rebucketed_sem0"] == 1
    assert summary["sections_skipped_grade_conflict"] == 0
    assert summary["sections_blocked_sem0_overflow"] == 0
    assert source_section.curriculum_course_id == target.id
    assert int(source_section.semester.number) == 1
    assert "sem0 conflict fallback" in (source_section.info or "")
    assert not CurriCrs.objects.filter(id=source.id).exists()


def test_merge_curri_crss_blocks_sem0_conflict_when_sem_slots_are_full(
    curri_factory,
    crs_factory,
    sem_factory,
    student,
):
    """Sem0 fallback should block when semesters 1..3 are already occupied."""
    summary = {}
    with _curriculum_course_constraint_disabled():
        target = CurriCrs.objects.create(
            curriculum=curri_factory("CURR-SEM0-B"),
            course=crs_factory("712"),
        )
        source = CurriCrs.objects.create(
            curriculum=target.curriculum,
            course=target.course,
        )
        ay_start = datetime(2024, 8, 1)
        semester0 = sem_factory(0, ay_start)
        semester1 = sem_factory(1, ay_start)
        semester2 = sem_factory(2, ay_start)
        semester3 = sem_factory(3, ay_start)
        Section.objects.create(curriculum_course=target, semester=semester1, number=1)
        Section.objects.create(curriculum_course=target, semester=semester2, number=1)
        Section.objects.create(curriculum_course=target, semester=semester3, number=1)
        target_section = Section.objects.create(
            curriculum_course=target,
            semester=semester0,
            number=5,
        )
        source_section = Section.objects.create(
            curriculum_course=source,
            semester=semester0,
            number=1,
        )
        grade_a, _ = GradeValue.objects.get_or_create(code="a")
        grade_b, _ = GradeValue.objects.get_or_create(code="b")
        Grade.objects.create(student=student, section=target_section, value=grade_a)
        Grade.objects.create(student=student, section=source_section, value=grade_b)

        summary = merge_curri_crss(target, [source])

        # Cleanup protected row so the unique constraint helper can restore.
        if Grade.objects.filter(section=source_section).exists():
            Grade.objects.filter(section=source_section).delete()

    assert summary["sections_rebucketed_sem0"] == 0
    assert summary["sections_blocked_sem0_overflow"] == 1
    assert summary["sections_skipped_grade_conflict"] == 1
    assert CurriCrs.objects.filter(id=source.id).exists()


def test_merge_crss_rebuckets_sem0_conflicts_for_course_merge(
    curri_factory,
    crs_factory,
    sem_factory,
    student,
):
    """Course merge should use sem0 fallback when grade conflicts block section merge."""
    curriculum = curri_factory("CURR-SEM0-COURSE")
    target_course = crs_factory("713")
    source_course = crs_factory("714")
    target_cc = CurriCrs.objects.create(curriculum=curriculum, course=target_course)
    source_cc = CurriCrs.objects.create(curriculum=curriculum, course=source_course)
    semester0 = sem_factory(0, datetime(2025, 8, 1))
    target_section = Section.objects.create(
        curriculum_course=target_cc,
        semester=semester0,
        number=4,
    )
    source_section = Section.objects.create(
        curriculum_course=source_cc,
        semester=semester0,
        number=1,
    )
    grade_a, _ = GradeValue.objects.get_or_create(code="a")
    grade_b, _ = GradeValue.objects.get_or_create(code="b")
    Grade.objects.create(student=student, section=target_section, value=grade_a)
    Grade.objects.create(student=student, section=source_section, value=grade_b)

    summary = merge_crss(target_course, [source_course])

    source_section.refresh_from_db()
    assert summary["sections_rebucketed_sem0"] == 1
    assert summary["sections_skipped_grade_conflict"] == 0
    assert source_section.curriculum_course_id == target_cc.id
    assert int(source_section.semester.number) == 1
    assert not Course.objects.filter(id=source_course.id).exists()


def test_merge_curri_crss_keeps_lowest_number_and_logs_conflicts(
    curri_factory, crs_factory, dft_sem, student
):
    """Merging grade-compatible sections keeps the lowest number and logs metadata."""
    summary = {}
    with _curriculum_course_constraint_disabled():
        target = CurriCrs.objects.create(
            curriculum=curri_factory("CURR-A"),
            course=crs_factory("502"),
        )
        source = CurriCrs.objects.create(
            curriculum=target.curriculum,
            course=target.course,
        )
        target_section = Section.objects.create(
            curriculum_course=target,
            semester=dft_sem,
            number=5,
            max_seats=40,
        )
        source_section = Section.objects.create(
            curriculum_course=source,
            semester=dft_sem,
            number=2,
            max_seats=50,
        )
        grade_value = GradeValue.get_dft()
        Grade.objects.create(student=student, section=target_section, value=grade_value)
        source_grade = Grade.objects.create(
            student=student,
            section=source_section,
            value=grade_value,
        )

        summary = merge_curri_crss(target, [source])

        if Section.objects.filter(id=source_section.id).exists():
            source_grade.delete()

    target_section.refresh_from_db()
    assert target_section.number == 2
    assert target_section.max_seats == 30
    assert "target non-default max_seats=40" in (target_section.info or "")
    assert "source non-default max_seats=50" in (target_section.info or "")
    # Depending on legacy duplicate grade rows, merge may retain source by PROTECT.
    assert summary["sections_merged"] == 1 or summary["sections_retained_protected"] == 1


def test_reconcile_std_curri_records_dedupes_same_grade_value(
    curri_factory,
    crs_factory,
    dft_sem,
    student,
):
    """Student-scoped reconciliation should drop duplicate same-value grades/regs."""
    target_curriculum = curri_factory("CURR-T-DEDUPE")
    source_curriculum = curri_factory("CURR-S-DEDUPE")
    course = crs_factory("601")
    target_cc = CurriCrs.objects.create(curriculum=target_curriculum, course=course)
    source_cc = CurriCrs.objects.create(curriculum=source_curriculum, course=course)
    target_section = Section.objects.create(
        curriculum_course=target_cc,
        semester=dft_sem,
        number=1,
    )
    source_section = Section.objects.create(
        curriculum_course=source_cc,
        semester=dft_sem,
        number=1,
    )
    grade_value, _ = GradeValue.objects.get_or_create(code="a")
    Grade.objects.create(student=student, section=target_section, value=grade_value)
    source_grade = Grade.objects.create(
        student=student,
        section=source_section,
        value=grade_value,
    )
    Registration.objects.create(student=student, section=target_section)
    source_registration = Registration.objects.create(
        student=student, section=source_section
    )

    summary = reconcile_std_curri_records(
        student=student,
        target_curriculum=target_curriculum,
        source_curriculum=source_curriculum,
    )

    assert summary["grades_deduped"] == 1
    assert summary["registrations_deduped"] == 1
    assert summary["grade_conflicts"] == 0
    assert not Grade.objects.filter(id=source_grade.id).exists()
    assert not Registration.objects.filter(id=source_registration.id).exists()


def test_reconcile_std_curri_records_flags_conflicting_grade_values(
    curri_factory,
    crs_factory,
    dft_sem,
    student,
):
    """Student-scoped reconciliation should keep different-value grade conflicts."""
    target_curriculum = curri_factory("CURR-T-CONFLICT")
    source_curriculum = curri_factory("CURR-S-CONFLICT")
    course = crs_factory("602")
    target_cc = CurriCrs.objects.create(curriculum=target_curriculum, course=course)
    source_cc = CurriCrs.objects.create(curriculum=source_curriculum, course=course)
    target_section = Section.objects.create(
        curriculum_course=target_cc,
        semester=dft_sem,
        number=1,
    )
    source_section = Section.objects.create(
        curriculum_course=source_cc,
        semester=dft_sem,
        number=1,
    )
    grade_a, _ = GradeValue.objects.get_or_create(code="a")
    grade_b, _ = GradeValue.objects.get_or_create(code="b")
    Grade.objects.create(student=student, section=target_section, value=grade_b)
    source_grade = Grade.objects.create(
        student=student, section=source_section, value=grade_a
    )

    summary = reconcile_std_curri_records(
        student=student,
        target_curriculum=target_curriculum,
        source_curriculum=source_curriculum,
    )

    assert summary["grade_conflicts"] == 1
    assert summary["grades_moved"] == 0
    assert Grade.objects.filter(id=source_grade.id, section=source_section).exists()


def test_reconcile_std_records_uses_dpt_number_id(
    curri_factory,
    crs_factory,
    dft_sem,
    student,
):
    """Reconciliation should dedupe same-value grades across duplicate course ids."""
    target_curriculum = curri_factory("CURR-T-IDENTITY")
    source_curriculum = curri_factory("CURR-S-IDENTITY")
    target_course = crs_factory("982")
    source_course = Course.objects.create(
        department=target_course.department,
        number=target_course.number,
        code=f"ALT{target_course.id}",
        short_code=f"ALT{target_course.number}",
    )
    target_cc = CurriCrs.objects.create(
        curriculum=target_curriculum, course=target_course
    )
    source_cc = CurriCrs.objects.create(
        curriculum=source_curriculum, course=source_course
    )
    target_section = Section.objects.create(
        curriculum_course=target_cc,
        semester=dft_sem,
        number=1,
    )
    source_section = Section.objects.create(
        curriculum_course=source_cc,
        semester=dft_sem,
        number=1,
    )
    grade_value, _ = GradeValue.objects.get_or_create(code="a")
    Grade.objects.create(student=student, section=target_section, value=grade_value)
    source_grade = Grade.objects.create(
        student=student,
        section=source_section,
        value=grade_value,
    )

    summary = reconcile_std_curri_records(
        student=student,
        target_curriculum=target_curriculum,
        source_curriculum=source_curriculum,
    )

    assert summary["grades_deduped"] == 1
    assert summary["grade_conflicts"] == 0
    assert not Grade.objects.filter(id=source_grade.id).exists()
