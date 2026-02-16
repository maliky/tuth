"""Course and curriculum-course merge operations."""

from __future__ import annotations

from django.db import transaction
from django.db.models import Q
from django.db.models.deletion import ProtectedError

from app.academics.models.course import Course
from app.academics.models.curriculum_course import CurriCourse
from app.academics.models.prerequisite import Prerequisite
from app.finance.models.invoice import Invoice
from app.timetable.models.section import Section

from .helpers import CourseMergeSummaryT, _merge_curri_crs_links
from .section_merge import (
    _merge_curri_crs_to_target,
    _merge_secs,
    _pick_sec_merge_candidate,
)


def _select_crs_merge_target(courses: list[Course]) -> Course:
    """Pick a target course based on description or smallest id."""
    # Prefer the course with a description, otherwise default to the smallest id.
    with_description = [
        course for course in courses if course.description and course.description.strip()
    ]
    candidates = with_description or courses
    sorted_candidates = sorted(candidates, key=lambda course: course.id or 0)[0]
    # problem if no course has a descriptionthis will be empty.
    return sorted_candidates


@transaction.atomic
def merge_courses(target: Course, sources):
    """Merge source courses into the target course."""
    summary = {
        "merged": 0,
        "skipped_invoices": 0,
        "curriculum_courses_moved": 0,
        "curriculum_courses_merged": 0,
        "sections_moved": 0,
        "sections_merged": 0,
        "prerequisites_moved": 0,
        "prerequisites_skipped": 0,
        "sections_retained_protected": 0,
        "sections_skipped_grade_conflict": 0,
        "protected_deletes": 0,
    }
    target_cc_map = {
        cc.curriculum_id: cc
        for cc in CurriCourse.objects.filter(course=target).select_related("curriculum")
    }
    for src in sources:
        if src.pk == target.pk:
            continue
        source_curriculum_courses = list(
            CurriCourse.objects.filter(course=src).select_related("curriculum")
        )
        if _crs_merge_has_invoice_conflict(source_curriculum_courses, target_cc_map):
            summary["skipped_invoices"] += 1
            continue
        # Merge or move curriculum courses before deleting the source course.
        for cc in source_curriculum_courses:
            curriculum_id = cc.curriculum_id
            existing = target_cc_map.get(curriculum_id)
            if existing:
                moved = _merge_curri_crs_to_target(existing, cc)
                summary["sections_moved"] += moved["sections_moved"]
                summary["sections_merged"] += moved["sections_merged"]
                summary["sections_retained_protected"] += moved[
                    "sections_retained_protected"
                ]
                summary["sections_skipped_grade_conflict"] += moved[
                    "sections_skipped_grade_conflict"
                ]
                summary["protected_deletes"] += moved["source_retained_protected"]
                summary["curriculum_courses_merged"] += 1
                continue
            cc.course = target
            cc.save(update_fields=["course"])
            target_cc_map[curriculum_id] = cc
            summary["curriculum_courses_moved"] += 1
        prereq_summary = _merge_crs_prerequisites(target, src)
        summary["prerequisites_moved"] += prereq_summary["prerequisites_moved"]
        summary["prerequisites_skipped"] += prereq_summary["prerequisites_skipped"]
        try:
            src.delete()
        except ProtectedError:
            summary["protected_deletes"] += 1
            continue
        summary["merged"] += 1
    return summary


def _crs_merge_has_invoice_conflict(
    source_curriculum_courses: list[CurriCourse],
    target_cc_map: dict[int, CurriCourse],
) -> bool:
    """Return True when invoices block merging source curriculum courses."""
    conflict_ids = [
        cc.id for cc in source_curriculum_courses if cc.curriculum_id in target_cc_map
    ]
    if not conflict_ids:
        return False
    return Invoice.objects.filter(curriculum_course_id__in=conflict_ids).exists()


def merge_curriculum_course_into_target(
    target: CurriCourse, source: CurriCourse
) -> dict[str, int]:
    """Merge one source curriculum-course into a target duplicate row.

    This helper is used by bulk curriculum reassignment where source and target
    can belong to different curricula but reference the same course.
    """
    summary = {
        "merged": 0,
        "skipped_incompatible": 0,
        "skipped_invoices": 0,
        "sections_moved": 0,
        "sections_merged": 0,
        "sections_retained_protected": 0,
        "sections_skipped_grade_conflict": 0,
        "protected_deletes": 0,
    }
    if source.pk == target.pk:
        return summary
    if source.course_id != target.course_id:
        summary["skipped_incompatible"] += 1
        return summary
    if Invoice.objects.filter(curriculum_course=source).exists():
        summary["skipped_invoices"] += 1
        return summary
    merge_result = _merge_curri_crs_to_target(target, source)
    summary["sections_moved"] += merge_result["sections_moved"]
    summary["sections_merged"] += merge_result["sections_merged"]
    summary["sections_retained_protected"] += merge_result["sections_retained_protected"]
    summary["sections_skipped_grade_conflict"] += merge_result[
        "sections_skipped_grade_conflict"
    ]
    summary["protected_deletes"] += merge_result["source_retained_protected"]
    if merge_result["source_retained_protected"] == 0:
        summary["merged"] += 1
    return summary


def _merge_crs_prerequisites(target: Course, source: Course) -> dict[str, int]:
    """Reassign prerequisite rows from the source course to the target course."""
    summary = {"prerequisites_moved": 0, "prerequisites_skipped": 0}
    prerequisites = list(
        Prerequisite.objects.filter(Q(course=source) | Q(prerequisite_course=source))
    )
    for prereq in prerequisites:
        new_course_id = target.id if prereq.course_id == source.id else prereq.course_id
        new_prereq_id = (
            target.id
            if prereq.prerequisite_course_id == source.id
            else prereq.prerequisite_course_id
        )
        if new_course_id == new_prereq_id:
            prereq.delete()
            summary["prerequisites_skipped"] += 1
            continue
        curriculum_id = prereq.curriculum_id
        if curriculum_id is None:
            has_duplicate = (
                Prerequisite.objects.filter(
                    curriculum__isnull=True,
                    course_id=new_course_id,
                    prerequisite_course_id=new_prereq_id,
                )
                .exclude(pk=prereq.pk)
                .exists()
            )
        else:
            has_duplicate = (
                Prerequisite.objects.filter(
                    curriculum_id=curriculum_id,
                    course_id=new_course_id,
                    prerequisite_course_id=new_prereq_id,
                )
                .exclude(pk=prereq.pk)
                .exists()
            )
        if has_duplicate:
            prereq.delete()
            summary["prerequisites_skipped"] += 1
            continue
        if (
            new_course_id != prereq.course_id
            or new_prereq_id != prereq.prerequisite_course_id
        ):
            prereq.course_id = new_course_id
            prereq.prerequisite_course_id = new_prereq_id
            prereq.save(update_fields=["course", "prerequisite_course"])
            summary["prerequisites_moved"] += 1
    return summary


@transaction.atomic
def merge_curriculum_courses(target: CurriCourse, sources):
    """Merge CurriCourse rows into target."""
    summary = {
        "merged": 0,
        "skipped_incompatible": 0,
        "skipped_invoices": 0,
        "sections_moved": 0,
        "sections_merged": 0,
        "credit_hours_conflicts": 0,
        "is_required_conflicts": 0,
        "is_elective_conflicts": 0,
        "sections_retained_protected": 0,
        "sections_skipped_grade_conflict": 0,
        "protected_deletes": 0,
    }
    for src in sources:
        if src.pk == target.pk:
            continue
        if src.curriculum_id != target.curriculum_id:
            summary["skipped_incompatible"] += 1
            continue
        if src.course_id != target.course_id:
            summary["skipped_incompatible"] += 1
            continue
        if Invoice.objects.filter(curriculum_course=src).exists():
            summary["skipped_invoices"] += 1
            continue
        if src.credit_hours_id != target.credit_hours_id:
            summary["credit_hours_conflicts"] += 1
        if src.is_required != target.is_required:
            summary["is_required_conflicts"] += 1
        if src.is_elective != target.is_elective:
            summary["is_elective_conflicts"] += 1
        _merge_curri_crs_links(target, src)
        source_sections = Section.objects.filter(curriculum_course=src)
        for section in source_sections:
            conflict = _pick_sec_merge_candidate(target, section)
            if conflict is not None:
                merge_result = _merge_secs(conflict, section)
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
            src.delete()
        except ProtectedError:
            summary["protected_deletes"] += 1
            continue
        summary["merged"] += 1
    return summary
