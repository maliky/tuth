"""Section and section-conflict merge helpers."""

from __future__ import annotations

from collections import defaultdict
from typing import cast

from django.db import models
from django.db.models.deletion import ProtectedError

from app.academics.models.curriculum_course import CurriCrs
from app.registry.models.grade import Grade
from app.registry.models.registration import Registration
from app.timetable.models.semester import Semester
from app.timetable.models.section import Section

from .helpers import SectionMergeResultT, _merge_curri_crs_links


def _merge_curri_crs_to_target(target: CurriCrs, source: CurriCrs) -> dict[str, int]:
    """Move section and concentration links from source to target."""
    summary = {
        "sections_moved": 0,
        "sections_merged": 0,
        "sections_retained_protected": 0,
        "sections_skipped_grade_conflict": 0,
        "sections_rebucketed_sem0": 0,
        "sections_blocked_sem0_overflow": 0,
        "source_retained_protected": 0,
    }
    _merge_curri_crs_links(target, source)
    # Freeze source sections before editing rows to avoid queryset drift.
    source_sections = list(
        Section.objects.filter(curriculum_course=source)
        .select_related("semester__academic_year", "curriculum_course__course")
        .order_by("id")
    )
    for section in source_sections:
        conflict = _pick_sec_merge_candidate(target, section)
        if conflict is not None:
            merge_result = _merge_secs(conflict, section)
            if merge_result["sections_merged"]:
                summary["sections_merged"] += merge_result["sections_merged"]
            elif merge_result["sections_skipped_grade_conflict"]:
                rebucketed, blocked_overflow = _rebucket_sem0_conflicting_section(
                    target,
                    section,
                    conflict,
                )
                if rebucketed:
                    summary["sections_rebucketed_sem0"] += 1
                    summary["sections_moved"] += 1
                else:
                    summary["sections_skipped_grade_conflict"] += merge_result[
                        "sections_skipped_grade_conflict"
                    ]
                    if blocked_overflow:
                        summary["sections_blocked_sem0_overflow"] += 1
            else:
                summary["sections_retained_protected"] += merge_result[
                    "sections_retained_protected"
                ]
            continue
        section.curriculum_course = target
        section.save(update_fields=["curriculum_course"])
        summary["sections_moved"] += 1
    try:
        source.delete()
    except ProtectedError:
        summary["source_retained_protected"] += 1
    return summary


def _is_sem0_section(section: Section) -> bool:
    """Return True when a section belongs to a semester number 0 placeholder."""
    return int(getattr(section.semester, "number", 0) or 0) == 0


def _sem_rebucket_slots(source_semester_id: int) -> dict[int, Semester]:
    """Return semester slots 1..3 for the source section academic year."""
    source_semester = Semester.objects.select_related("academic_year").get(
        id=source_semester_id
    )
    academic_year = source_semester.academic_year
    slots: dict[int, Semester] = {}
    for sem_number in (1, 2, 3):
        semester, _ = Semester.objects.get_or_create(
            academic_year=academic_year,
            number=sem_number,
        )
        slots[sem_number] = semester
    return slots


def _rebucket_sem0_conflicting_section(
    target_curriculum_course: CurriCrs,
    source_section: Section,
    conflict_section: Section,
) -> tuple[bool, bool]:
    """Reassign one sem0 conflicting section into semester 1..3 and target course.

    Returns:
        (rebucketed, blocked_overflow)
    """
    if not (_is_sem0_section(source_section) and _is_sem0_section(conflict_section)):
        return False, False

    slot_by_number = _sem_rebucket_slots(source_section.semester_id)
    slot_ids = [semester.id for semester in slot_by_number.values()]
    used_slot_ids = set(
        Section.objects.filter(
            curriculum_course=target_curriculum_course,
            semester_id__in=slot_ids,
        ).values_list("semester_id", flat=True)
    )
    source_course_id = int(source_section.curriculum_course.course_id)
    target_course_id = int(target_curriculum_course.course_id)
    affected_student_ids = set(
        Grade.objects.filter(section=source_section).values_list("student_id", flat=True)
    )

    for sem_number in (1, 2, 3):
        semester = slot_by_number[sem_number]
        if semester.id in used_slot_ids:
            continue

        source_section.curriculum_course = target_curriculum_course
        source_section.semester = semester
        note = (
            "[merge] sem0 conflict fallback: moved from "
            f"semester={conflict_section.semester_id} to semester={semester.id}"
        )
        source_section.info = f"{source_section.info}\n{note}".strip()
        source_section.save(update_fields=["curriculum_course", "semester", "info"])

        for student_id in affected_student_ids:
            Grade.recompute_effective_for_student_course(
                student_id=int(student_id),
                course_id=target_course_id,
            )
            if source_course_id != target_course_id:
                Grade.recompute_effective_for_student_course(
                    student_id=int(student_id),
                    course_id=source_course_id,
                )
        return True, False

    # No slot available in 1..3 for sem0 fallback.
    return False, True


def _pick_sec_merge_candidate(
    target_curriculum_course: CurriCrs,
    source_section: Section,
) -> Section | None:
    """Return a deterministic section merge candidate for a source section."""
    same_number = Section.objects.filter(
        curriculum_course=target_curriculum_course,
        semester_id=source_section.semester_id,
        number=source_section.number,
    ).first()
    if same_number is not None:
        return same_number
    # > If only one target section exists in the semester, treat it as candidate.
    same_semester = list(
        Section.objects.filter(
            curriculum_course=target_curriculum_course,
            semester_id=source_section.semester_id,
        ).order_by("number", "id")[:2]
    )
    if len(same_semester) == 1:
        return same_semester[0]
    return None


def _index_sec_merge_candidates(
    sections: list[Section],
) -> tuple[dict[tuple[int, int], Section], dict[int, list[Section]]]:
    """Index target sections for deterministic merge-candidate resolution."""
    by_semester_number: dict[tuple[int, int], Section] = {}
    by_semester: dict[int, list[Section]] = defaultdict(list)
    for section in sections:
        by_semester_number[(section.semester_id, section.number)] = section
        by_semester[section.semester_id].append(section)
    return by_semester_number, by_semester


def _pick_sec_merge_candidate_from_index(
    source_section: Section,
    by_semester_number: dict[tuple[int, int], Section],
    by_semester: dict[int, list[Section]],
) -> Section | None:
    """Return merge candidate using in-memory indexes (no extra DB query)."""
    same_number = by_semester_number.get(
        (source_section.semester_id, source_section.number)
    )
    if same_number is not None:
        return same_number
    same_semester = by_semester.get(source_section.semester_id, [])
    if len(same_semester) == 1:
        return same_semester[0]
    return None


def _grade_value_map_for_sec(section: Section) -> dict[int, int | None]:
    """Return grade values keyed by student id for a section."""
    return {
        student_id: value_id
        for student_id, value_id in Grade.objects.filter(section=section).values_list(
            "student_id",
            "value_id",
        )
    }


def _has_mergeable_grade_overlap(target: Section, source: Section) -> bool:
    """Return True when overlapping student grades are compatible for merging."""
    target_grade_map = _grade_value_map_for_sec(target)
    source_grade_map = _grade_value_map_for_sec(source)
    overlapping_students = set(target_grade_map).intersection(source_grade_map)
    if not overlapping_students:
        return True
    for student_id in overlapping_students:
        if target_grade_map[student_id] != source_grade_map[student_id]:
            return False
    return True


def _sec_dft_value(field_name: str):
    """Return the effective default value for a section model field."""
    field = cast(models.Field, Section._meta.get_field(field_name))
    if field.has_default():
        return field.get_default()
    if getattr(field, "null", False):
        return None
    return None


def _is_non_dft_sec_value(field_name: str, value) -> bool:
    """Return True when a section field value differs from its default."""
    return bool(value != _sec_dft_value(field_name))


def _append_sec_merge_notes(target: Section, notes: list[str]) -> None:
    """Append structured merge notes to the target section info field."""
    if not notes:
        return
    existing_info = (target.info or "").strip()
    note_block = "\n".join(notes)
    target.info = (
        f"{existing_info}\n{note_block}".strip() if existing_info else note_block
    )


def _reconcile_sec_fields(target: Section, source: Section) -> list[str]:
    """Reconcile section metadata and return update_fields for saving target."""
    update_fields: set[str] = set()
    notes: list[str] = []

    lowest_number = min(int(target.number), int(source.number))
    if int(target.number) != lowest_number:
        target.number = lowest_number
        update_fields.add("number")
    if _is_non_dft_sec_value("number", source.number):
        notes.append(f"[merge] source non-default number={source.number}")
    if _is_non_dft_sec_value("number", target.number):
        notes.append(f"[merge] target non-default number={target.number}")

    field_names = ("faculty_id", "start_date", "end_date", "max_seats")
    for field_name in field_names:
        target_value = getattr(target, field_name)
        source_value = getattr(source, field_name)
        if target_value == source_value:
            if _is_non_dft_sec_value(field_name, target_value):
                notes.append(f"[merge] both non-default {field_name}={target_value}")
            continue

        target_non_default = _is_non_dft_sec_value(field_name, target_value)
        source_non_default = _is_non_dft_sec_value(field_name, source_value)
        if target_non_default:
            notes.append(f"[merge] target non-default {field_name}={target_value}")
        if source_non_default:
            notes.append(f"[merge] source non-default {field_name}={source_value}")

        if target_non_default and not source_non_default:
            continue
        if source_non_default and not target_non_default:
            setattr(target, field_name, source_value)
            update_fields.add(field_name.removesuffix("_id"))
            continue
        if target_non_default and source_non_default:
            setattr(target, field_name, _sec_dft_value(field_name))
            update_fields.add(field_name.removesuffix("_id"))

    _append_sec_merge_notes(target, notes)
    if notes:
        update_fields.add("info")
    return sorted(update_fields)


def _merge_secs(target: Section, source: Section) -> SectionMergeResultT:
    """Merge a conflicting section into target, moving related records."""
    if not _has_mergeable_grade_overlap(target, source):
        return {
            "sections_merged": 0,
            "sections_retained_protected": 0,
            "sections_skipped_grade_conflict": 1,
        }

    updated_fields = _reconcile_sec_fields(target, source)
    if updated_fields:
        target.save(update_fields=updated_fields)

    for session in source.sessions.all():
        schedule_id = session.schedule_id
        if schedule_id is not None:
            if target.sessions.filter(schedule_id=schedule_id).exists():
                continue
        session.section = target
        session.save(update_fields=["section"])

    target_grade_values: dict[int, int | None] = dict(
        Grade.objects.filter(section=target).values_list("student_id", "value_id")
    )
    affected_student_ids: set[int] = set()
    target_course_id = int(target.curriculum_course.course_id)
    for grade in Grade.objects.filter(section=source):
        affected_student_ids.add(int(grade.student_id))
        target_value_id = target_grade_values.get(grade.student_id)
        if target_value_id is not None:
            # Drop true duplicates so source section can be deleted safely.
            if target_value_id == grade.value_id:
                grade.delete(recompute_effective=False)
            continue
        grade.section = target
        # Defer effective recompute until all section-grade moves are done.
        grade.save(update_fields=["section"], recompute_effective=False)
        target_grade_values[grade.student_id] = grade.value_id
    for student_id in affected_student_ids:
        Grade.recompute_effective_for_student_course(
            student_id=student_id,
            course_id=target_course_id,
        )

    for registration in Registration.objects.filter(section=source):
        if Registration.objects.filter(
            section=target, student_id=registration.student_id
        ).exists():
            continue
        registration.section = target
        registration.save(update_fields=["section"])

    try:
        source.delete()
        return {
            "sections_merged": 1,
            "sections_retained_protected": 0,
            "sections_skipped_grade_conflict": 0,
        }
    except ProtectedError:
        return {
            "sections_merged": 0,
            "sections_retained_protected": 1,
            "sections_skipped_grade_conflict": 0,
        }
