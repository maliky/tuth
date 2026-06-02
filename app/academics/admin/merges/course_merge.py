"""Course and curriculum-course merge operations."""

from __future__ import annotations

from django.db import transaction
from django.db.models import Q
from django.db.models.deletion import ProtectedError

from app.academics.models.course import Course
from app.academics.models.curriculum_course import CurriCrs
from app.academics.models.prerequisite import Prerequisite
from app.finance.models.invoice import Invoice
from app.registry.models.grade import Grade
from app.registry.models.registration import Registration
from app.timetable.models.section import Section

from .helpers import CrsMergeSummaryT
from .section_merge import _merge_curri_crs_to_target


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


def _sec_student_ids(section: Section) -> set[int]:
    """Return students with grade or registration records on a section."""
    grade_student_ids = Grade.objects.filter(section=section).values_list(
        "student_id", flat=True
    )
    registration_student_ids = Registration.objects.filter(section=section).values_list(
        "student_id", flat=True
    )
    return {int(student_id) for student_id in grade_student_ids}.union(
        int(student_id) for student_id in registration_student_ids
    )


def _has_sec_student_overlap(target: Section, source: Section) -> bool:
    """Return True when two sections share grade or registration students."""
    return bool(_sec_student_ids(target).intersection(_sec_student_ids(source)))


def _pick_duplicate_curri_crs_sec_candidate(
    target_curriculum_course: CurriCrs,
    source_section: Section,
) -> Section | None:
    """Pick a section merge candidate for duplicate CurriCrs rows.

    Same-number sections are duplicate offerings and should merge. Different
    section numbers should remain distinct unless student records overlap.
    """
    same_number = Section.objects.filter(
        curriculum_course=target_curriculum_course,
        semester_id=source_section.semester_id,
        number=source_section.number,
    ).first()
    if same_number is not None:
        return same_number

    same_semester = list(
        Section.objects.filter(
            curriculum_course=target_curriculum_course,
            semester_id=source_section.semester_id,
        ).order_by("number", "id")[:2]
    )
    if len(same_semester) == 1 and _has_sec_student_overlap(
        same_semester[0], source_section
    ):
        return same_semester[0]
    return None


@transaction.atomic
def merge_crss(target: Course, sources):
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
        "sections_rebucketed_sem0": 0,
        "sections_blocked_sem0_overflow": 0,
        "protected_deletes": 0,
    }
    target_cc_map = {
        cc.curriculum_id: cc
        for cc in CurriCrs.objects.filter(course=target).select_related("curriculum")
    }
    for src in sources:
        if src.pk == target.pk:
            continue
        source_curriculum_courses = list(
            CurriCrs.objects.filter(course=src).select_related("curriculum")
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
                summary["sections_rebucketed_sem0"] += moved["sections_rebucketed_sem0"]
                summary["sections_blocked_sem0_overflow"] += moved[
                    "sections_blocked_sem0_overflow"
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
    source_curriculum_courses: list[CurriCrs],
    target_cc_map: dict[int, CurriCrs],
) -> bool:
    """Return True when invoices block merging source curriculum courses."""
    conflict_ids = [
        cc.id for cc in source_curriculum_courses if cc.curriculum_id in target_cc_map
    ]
    if not conflict_ids:
        return False
    return Invoice.objects.filter(curriculum_course_id__in=conflict_ids).exists()


def merge_curri_crs_into_target(target: CurriCrs, source: CurriCrs) -> dict[str, int]:
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
        "sections_rebucketed_sem0": 0,
        "sections_blocked_sem0_overflow": 0,
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
    summary["sections_rebucketed_sem0"] += merge_result["sections_rebucketed_sem0"]
    summary["sections_blocked_sem0_overflow"] += merge_result[
        "sections_blocked_sem0_overflow"
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
def merge_curri_crss(target: CurriCrs, sources):
    """Merge CurriCrs rows into target."""
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
        "sections_rebucketed_sem0": 0,
        "sections_blocked_sem0_overflow": 0,
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
        # Use the shared curriculum-course merge path so section conflict
        # rebucketing and protected-delete counters stay consistent.
        merge_result = _merge_curri_crs_to_target(
            target,
            src,
            candidate_selector=_pick_duplicate_curri_crs_sec_candidate,
        )
        summary["sections_moved"] += merge_result["sections_moved"]
        summary["sections_merged"] += merge_result["sections_merged"]
        summary["sections_retained_protected"] += merge_result[
            "sections_retained_protected"
        ]
        summary["sections_skipped_grade_conflict"] += merge_result[
            "sections_skipped_grade_conflict"
        ]
        summary["sections_rebucketed_sem0"] += merge_result["sections_rebucketed_sem0"]
        summary["sections_blocked_sem0_overflow"] += merge_result[
            "sections_blocked_sem0_overflow"
        ]
        summary["protected_deletes"] += merge_result["source_retained_protected"]
        if merge_result["source_retained_protected"] == 0:
            summary["merged"] += 1
    return summary
