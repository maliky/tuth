"""Section and section-conflict merge helpers."""

from __future__ import annotations

from collections import defaultdict
from typing import cast

from django.db import models
from django.db.models.deletion import ProtectedError

from app.academics.models.curriculum_course import CurriCourse
from app.registry.models.grade import Grade
from app.registry.models.registration import Registration
from app.timetable.models.section import Section

from .helpers import SectionMergeResultT, _merge_curriculum_course_links


def _merge_curriculum_course_to_target(
    target: CurriCourse, source: CurriCourse
) -> dict[str, int]:
    """Move section and concentration links from source to target."""
    summary = {
        "sections_moved": 0,
        "sections_merged": 0,
        "sections_retained_protected": 0,
        "sections_skipped_grade_conflict": 0,
        "source_retained_protected": 0,
    }
    _merge_curriculum_course_links(target, source)
    source_sections = Section.objects.filter(curriculum_course=source)
    for section in source_sections:
        conflict = _pick_section_merge_candidate(target, section)
        if conflict is not None:
            merge_result = _merge_sections(conflict, section)
            if merge_result["sections_merged"]:
                summary["sections_merged"] += merge_result["sections_merged"]
            elif merge_result["sections_skipped_grade_conflict"]:
                summary["sections_skipped_grade_conflict"] += merge_result[
                    "sections_skipped_grade_conflict"
                ]
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


def _pick_section_merge_candidate(
    target_curriculum_course: CurriCourse,
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


def _index_section_merge_candidates(
    sections: list[Section],
) -> tuple[dict[tuple[int, int], Section], dict[int, list[Section]]]:
    """Index target sections for deterministic merge-candidate resolution."""
    by_semester_number: dict[tuple[int, int], Section] = {}
    by_semester: dict[int, list[Section]] = defaultdict(list)
    for section in sections:
        by_semester_number[(section.semester_id, section.number)] = section
        by_semester[section.semester_id].append(section)
    return by_semester_number, by_semester


def _pick_section_merge_candidate_from_index(
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


def _grade_value_map_for_section(section: Section) -> dict[int, int | None]:
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
    target_grade_map = _grade_value_map_for_section(target)
    source_grade_map = _grade_value_map_for_section(source)
    overlapping_students = set(target_grade_map).intersection(source_grade_map)
    if not overlapping_students:
        return True
    for student_id in overlapping_students:
        if target_grade_map[student_id] != source_grade_map[student_id]:
            return False
    return True


def _section_default_value(field_name: str):
    """Return the effective default value for a section model field."""
    field = cast(models.Field, Section._meta.get_field(field_name))
    if field.has_default():
        return field.get_default()
    if getattr(field, "null", False):
        return None
    return None


def _is_non_default_section_value(field_name: str, value) -> bool:
    """Return True when a section field value differs from its default."""
    return bool(value != _section_default_value(field_name))


def _append_section_merge_notes(target: Section, notes: list[str]) -> None:
    """Append structured merge notes to the target section info field."""
    if not notes:
        return
    existing_info = (target.info or "").strip()
    note_block = "\n".join(notes)
    target.info = (
        f"{existing_info}\n{note_block}".strip() if existing_info else note_block
    )


def _reconcile_section_fields(target: Section, source: Section) -> list[str]:
    """Reconcile section metadata and return update_fields for saving target."""
    update_fields: set[str] = set()
    notes: list[str] = []

    lowest_number = min(int(target.number), int(source.number))
    if int(target.number) != lowest_number:
        target.number = lowest_number
        update_fields.add("number")
    if _is_non_default_section_value("number", source.number):
        notes.append(f"[merge] source non-default number={source.number}")
    if _is_non_default_section_value("number", target.number):
        notes.append(f"[merge] target non-default number={target.number}")

    field_names = ("faculty_id", "start_date", "end_date", "max_seats")
    for field_name in field_names:
        target_value = getattr(target, field_name)
        source_value = getattr(source, field_name)
        if target_value == source_value:
            if _is_non_default_section_value(field_name, target_value):
                notes.append(f"[merge] both non-default {field_name}={target_value}")
            continue

        target_non_default = _is_non_default_section_value(field_name, target_value)
        source_non_default = _is_non_default_section_value(field_name, source_value)
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
            setattr(target, field_name, _section_default_value(field_name))
            update_fields.add(field_name.removesuffix("_id"))

    _append_section_merge_notes(target, notes)
    if notes:
        update_fields.add("info")
    return sorted(update_fields)


def _merge_sections(target: Section, source: Section) -> SectionMergeResultT:
    """Merge a conflicting section into target, moving related records."""
    if not _has_mergeable_grade_overlap(target, source):
        return {
            "sections_merged": 0,
            "sections_retained_protected": 0,
            "sections_skipped_grade_conflict": 1,
        }

    updated_fields = _reconcile_section_fields(target, source)
    if updated_fields:
        target.save(update_fields=updated_fields)

    for session in source.sessions.all():
        schedule_id = session.schedule_id
        if schedule_id is not None:
            if target.sessions.filter(schedule_id=schedule_id).exists():
                continue
        session.section = target
        session.save(update_fields=["section"])

    for grade in Grade.objects.filter(section=source):
        if Grade.objects.filter(section=target, student_id=grade.student_id).exists():
            continue
        grade.section = target
        grade.save(update_fields=["section"])

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
