"""Student duplicate audit and merge regressions."""

from __future__ import annotations

import pytest
from django.contrib.auth.models import User

from app.people.models.student import Student
from app.people.models.student_curriculum_enrollment import set_primary_std_curri_enroll
from app.people.services.student_duplicate_merge import safe_merge_student
from app.people.services.student_duplicates import (
    duplicate_sources,
    student_duplicate_groups,
)
from app.registry.models.grade import Grade, GradeValue
from app.registry.models.registration import Registration
from app.shared.student_ids import (
    canonical_student_id,
    student_id_digit_key,
    student_id_exact_key,
)

pytestmark = pytest.mark.django_db


def _student(
    username: str,
    student_id: str,
    *,
    first_name: str,
    last_name: str,
    semester,
    curriculum,
) -> Student:
    """Create one persisted student with a controlled external id."""
    user = User.objects.create_user(
        username=username,
        first_name=first_name,
        last_name=last_name,
    )
    student = Student(
        user=user,
        student_id=student_id,
        entry_semester=semester,
        last_enrolled_semester=semester,
    )
    student.save()
    set_primary_std_curri_enroll(student, curriculum, entry_semester_id=semester.id)
    return student


def test_student_id_helpers_keep_exact_and_numeric_overlap_separate() -> None:
    """TU variants canonicalize; bare numeric ids remain a manual overlap."""
    assert canonical_student_id(" Tu-04047 ") == "TU-04047"
    assert canonical_student_id("04047") == "04047"
    assert student_id_exact_key("Tu-04047") == student_id_exact_key("TU-04047")
    assert student_id_exact_key("04047") != student_id_exact_key("TU-04047")
    assert student_id_digit_key("04047") == student_id_digit_key("TU-04047")


def test_safe_student_merge_moves_operational_rows_before_deleting_source(
    reg_sem_pair_factory,
    reg_sec_factory,
) -> None:
    """Exact-id merge should preserve source grades and registrations."""
    _academic_year, _previous, current = reg_sem_pair_factory()
    section, curriculum = reg_sec_factory(
        current,
        course_number="141",
        curriculum_short_name="CURRI_STUDENT_DUP",
    )
    target = _student(
        "eastline.clark",
        "TU-04047",
        first_name="Eastline",
        last_name="Clark",
        semester=current,
        curriculum=curriculum,
    )
    source = _student(
        "student.tu04047",
        "Tu-04047",
        first_name="Student",
        last_name="Tu-04047",
        semester=current,
        curriculum=curriculum,
    )
    Registration.objects.create(student=source, section=section)
    GradeValue._populate_attributes_and_db()
    Grade.objects.create(
        student=source,
        section=section,
        value=GradeValue.objects.get(code="a"),
    )

    [group] = student_duplicate_groups(kind="exact_id", student_id="TU-04047")
    plan_target, sources = duplicate_sources(group.students)
    dry_run = safe_merge_student(plan_target, sources[0])
    result = safe_merge_student(plan_target, sources[0], apply=True)

    assert plan_target.pk == target.pk
    assert sources == [source]
    assert dry_run.applied is False
    assert dry_run.conflicts == []
    assert result.applied is True
    assert Registration.objects.filter(student=target, section=section).exists()
    assert Grade.objects.filter(student=target, section=section).exists()
    assert not Student.objects.filter(pk=source.pk).exists()
    assert not User.objects.filter(username="student.tu04047").exists()


def test_safe_student_merge_blocks_section_collisions(
    reg_sem_pair_factory,
    reg_sec_factory,
) -> None:
    """A source row cannot overwrite an existing target section row."""
    _academic_year, _previous, current = reg_sem_pair_factory()
    section, curriculum = reg_sec_factory(
        current,
        course_number="142",
        curriculum_short_name="CURRI_STUDENT_DUP_COLLISION",
    )
    target = _student(
        "eastline.collision",
        "TU-04048",
        first_name="Eastline",
        last_name="Collision",
        semester=current,
        curriculum=curriculum,
    )
    source = _student(
        "student.tu04048",
        "tu-04048",
        first_name="Student",
        last_name="Tu-04048",
        semester=current,
        curriculum=curriculum,
    )
    Registration.objects.create(student=target, section=section)
    Registration.objects.create(student=source, section=section)

    result = safe_merge_student(target, source, apply=True)

    assert result.applied is False
    assert [conflict.model_name for conflict in result.conflicts] == ["Registration"]
    assert Student.objects.filter(pk=source.pk).exists()
