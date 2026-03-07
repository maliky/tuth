"""Curriculum merge and student enrollment reconciliation logic."""

from __future__ import annotations

from collections import defaultdict

from django.db import transaction
from django.db.models import Q
from django.db.models.deletion import ProtectedError

from app.academics.models.concentration import Major, Minor
from app.academics.models.curriculum import Curriculum
from app.academics.models.curriculum_course import CurriCrs
from app.academics.models.prerequisite import Prerequisite
from app.finance.models.invoice import Invoice
from app.people.models.student import Student
from app.people.models.student_curriculum_enrollment import StdCurriEnroll
from app.registry.models.grade import Grade
from app.registry.models.registration import Registration
from app.timetable.models.section import Section

from .helpers import (
    ConflictChoiceByCrsIdT,
    ConflictChoiceT,
    ConflictCurriCrsPairT,
    CrsIdityT,
    MERGE_CHOICE_KEEP_SOURCE,
    MERGE_CHOICE_KEEP_TARGET,
    MERGE_CHOICE_MERGE,
    MERGE_CHOICE_SKIP,
    StdCurriRecordMergeSummaryT,
    _build_crs_idity,
    _curri_crs_idity,
    _idity_by_curri_crs_id,
    _index_curri_crss_by_idity,
    _merge_curri_crs_links,
    empty_std_curri_record_summary,
)
from .section_merge import (
    _index_sec_merge_candidates,
    _merge_curri_crs_to_target,
    _pick_sec_merge_candidate_from_index,
)


def list_curri_crs_conflicts(
    target: Curriculum, source: Curriculum
) -> tuple[list[ConflictCurriCrsPairT], list[CurriCrs]]:
    """Return conflicting and non-conflicting programmed courses for two curricula."""
    target_rows = list(
        CurriCrs.objects.filter(curriculum=target)
        .select_related("course", "credit_hours")
        .order_by("id")
    )
    source_rows = list(
        CurriCrs.objects.filter(curriculum=source)
        .select_related("course", "credit_hours")
        .order_by("id")
    )
    # > Reconciliation uses canonical identity (department, number), not raw course id.
    target_by_course_identity = _index_curri_crss_by_idity(target_rows)
    conflicts: list[ConflictCurriCrsPairT] = []
    non_conflicting: list[CurriCrs] = []
    for source_row in source_rows:
        source_identity = _curri_crs_idity(source_row)
        target_row = (
            target_by_course_identity.get(source_identity)
            if source_identity is not None
            else None
        )
        if target_row is None:
            non_conflicting.append(source_row)
            continue
        conflicts.append((target_row, source_row))
    return conflicts, non_conflicting


def _overlay_curri_crs_fields(target: CurriCrs, source: CurriCrs) -> None:
    """Copy selected field values from source onto target before merge."""
    updated_fields: list[str] = []
    field_names = (
        "credit_hours_id",
        "is_required",
        "is_elective",
        "semester_number",
        "level_number",
        "year_number",
        "required_group_number",
        "min_validated_credits",
    )
    for field_name in field_names:
        source_value = getattr(source, field_name)
        if getattr(target, field_name) == source_value:
            continue
        setattr(target, field_name, source_value)
        updated_fields.append(field_name.removesuffix("_id"))
    if updated_fields:
        target.save(update_fields=updated_fields)


def _keep_target_curri_crs(target: CurriCrs, source: CurriCrs) -> dict[str, int]:
    """Keep target programmed course and delete source when possible."""
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
    try:
        source.delete()
    except ProtectedError:
        summary["source_retained_protected"] = 1
    return summary


def _merge_curri_crs_conflict(
    target: CurriCrs,
    source: CurriCrs,
    choice: ConflictChoiceT,
) -> dict[str, int]:
    """Resolve one conflicting programmed course pair with a caller-selected mode."""
    if choice == MERGE_CHOICE_SKIP:
        return {
            "sections_moved": 0,
            "sections_merged": 0,
            "sections_retained_protected": 0,
            "sections_skipped_grade_conflict": 0,
            "sections_rebucketed_sem0": 0,
            "sections_blocked_sem0_overflow": 0,
            "source_retained_protected": 0,
        }
    if choice == MERGE_CHOICE_KEEP_SOURCE:
        # Keep the target row id for FK stability, while applying source metadata.
        _overlay_curri_crs_fields(target, source)
        return _merge_curri_crs_to_target(target, source)
    if choice == MERGE_CHOICE_KEEP_TARGET:
        return _keep_target_curri_crs(target, source)
    return _merge_curri_crs_to_target(target, source)


def _move_std_enrollments_for_curri_merge(
    *,
    target: Curriculum,
    source: Curriculum,
) -> int:
    """Move source curriculum enrollments to target without duplicate rows."""
    moved_rows = 0
    source_rows = list(
        StdCurriEnroll.objects.filter(curriculum=source)
        .select_related("student", "curriculum")
        .order_by("id")
    )
    for source_row in source_rows:
        target_row = StdCurriEnroll.objects.filter(
            student_id=source_row.student_id,
            curriculum=target,
        ).first()
        if target_row is not None:
            merged, _ = merge_std_enrollment_pair(target_row, source_row)
            if merged:
                moved_rows += 1
            continue
        source_row.curriculum = target
        source_row.save(update_fields=["curriculum"])
        moved_rows += 1
    return moved_rows


@transaction.atomic
def merge_curra(
    target: Curriculum,
    sources,
    conflict_choices: ConflictChoiceByCrsIdT | None = None,
):
    """Merge curricula: move attached records to the target curriculum."""
    selected_choices: ConflictChoiceByCrsIdT = conflict_choices or {}
    summary = {
        "curricula_merged": 0,
        "curricula_retained": 0,
        "students_moved": 0,
        "curriculum_courses_moved": 0,
        "curriculum_courses_merged": 0,
        "sections_moved": 0,
        "sections_merged": 0,
        "prerequisites_moved": 0,
        "prerequisites_skipped": 0,
        "skipped_invoices": 0,
        "credit_hours_conflicts": 0,
        "is_required_conflicts": 0,
        "is_elective_conflicts": 0,
        "majors_moved": 0,
        "minors_moved": 0,
        "sections_retained_protected": 0,
        "sections_skipped_grade_conflict": 0,
        "sections_rebucketed_sem0": 0,
        "sections_blocked_sem0_overflow": 0,
        "protected_deletes": 0,
        "conflicts_kept_target": 0,
        "conflicts_kept_source": 0,
        "conflicts_merged": 0,
        "conflicts_skipped": 0,
    }
    for src in sources:
        if src.pk == target.pk:
            continue
        skip_delete = False
        target_rows = list(
            CurriCrs.objects.filter(curriculum=target)
            .select_related("course")
            .order_by("id")
        )
        target_by_course_identity = _index_curri_crss_by_idity(target_rows)
        moved_students = _move_std_enrollments_for_curri_merge(
            target=target,
            source=src,
        )
        summary["students_moved"] += moved_students
        summary["majors_moved"] += Major.objects.filter(curriculum=src).update(
            curriculum=target
        )
        summary["minors_moved"] += Minor.objects.filter(curriculum=src).update(
            curriculum=target
        )
        for prereq in Prerequisite.objects.filter(curriculum=src):
            if Prerequisite.objects.filter(
                curriculum=target,
                course_id=prereq.course_id,
                prerequisite_course_id=prereq.prerequisite_course_id,
            ).exists():
                prereq.delete()
                summary["prerequisites_skipped"] += 1
                continue
            prereq.curriculum = target
            prereq.save(update_fields=["curriculum"])
            summary["prerequisites_moved"] += 1
        for cc in CurriCrs.objects.filter(curriculum=src).select_related("course"):
            # > Avoid duplicate entries using canonical identity.
            source_identity = _curri_crs_idity(cc)
            existing = (
                target_by_course_identity.get(source_identity)
                if source_identity is not None
                else None
            )
            if existing:
                selected_choice = selected_choices.get(cc.course_id, MERGE_CHOICE_MERGE)
                if Invoice.objects.filter(curriculum_course=cc).exists():
                    summary["skipped_invoices"] += 1
                    skip_delete = True
                    continue
                if cc.credit_hours_id != existing.credit_hours_id:
                    summary["credit_hours_conflicts"] += 1
                if cc.is_required != existing.is_required:
                    summary["is_required_conflicts"] += 1
                if cc.is_elective != existing.is_elective:
                    summary["is_elective_conflicts"] += 1
                moved = _merge_curri_crs_conflict(
                    existing,
                    cc,
                    selected_choice,
                )
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
                if moved["source_retained_protected"]:
                    summary["protected_deletes"] += moved["source_retained_protected"]
                    skip_delete = True
                if selected_choice == MERGE_CHOICE_KEEP_TARGET:
                    summary["conflicts_kept_target"] += 1
                elif selected_choice == MERGE_CHOICE_KEEP_SOURCE:
                    summary["conflicts_kept_source"] += 1
                elif selected_choice == MERGE_CHOICE_SKIP:
                    summary["conflicts_skipped"] += 1
                    skip_delete = True
                else:
                    summary["conflicts_merged"] += 1
                summary["curriculum_courses_merged"] += 1
                continue
            cc.curriculum = target
            cc.save(update_fields=["curriculum"])
            if source_identity is not None:
                target_by_course_identity[source_identity] = cc
            summary["curriculum_courses_moved"] += 1
        if skip_delete:
            summary["curricula_retained"] += 1
            continue
        try:
            src.delete()
        except ProtectedError:
            summary["curricula_retained"] += 1
            summary["protected_deletes"] += 1
            continue
        summary["curricula_merged"] += 1
    return summary


def _entry_sem_merge_blocked(
    target_row: StdCurriEnroll,
    source_row: StdCurriEnroll,
) -> bool:
    """Return True when both rows have different non-null entry semesters."""
    target_entry_id = target_row.entry_semester_id
    source_entry_id = source_row.entry_semester_id
    return bool(
        target_entry_id and source_entry_id and target_entry_id != source_entry_id
    )


def merge_std_enrollment_pair(
    target_row: StdCurriEnroll,
    source_row: StdCurriEnroll,
) -> tuple[bool, StdCurriRecordMergeSummaryT]:
    """Merge one source enrollment row into a target enrollment row."""
    summary = empty_std_curri_record_summary()
    if target_row.student_id != source_row.student_id:
        return False, summary
    if _entry_sem_merge_blocked(target_row, source_row):
        return False, summary

    # Reconcile student-scoped grade/registration duplicates before row collapse.
    summary = reconcile_std_curri_records(
        student=target_row.student,
        target_curriculum=target_row.curriculum,
        source_curriculum=source_row.curriculum,
    )

    update_fields: list[str] = []
    if not target_row.entry_semester_id and source_row.entry_semester_id:
        target_row.entry_semester_id = source_row.entry_semester_id
        update_fields.append("entry_semester")
    if not target_row.exit_semester_id and source_row.exit_semester_id:
        target_row.exit_semester_id = source_row.exit_semester_id
        update_fields.append("exit_semester")
    if not target_row.is_primary and source_row.is_primary:
        target_row.is_primary = True
        update_fields.append("is_primary")
    if not target_row.is_active and source_row.is_active:
        target_row.is_active = True
        update_fields.append("is_active")
    if target_row.creation_date > source_row.creation_date:
        target_row.creation_date = source_row.creation_date
        update_fields.append("creation_date")

    if target_row.is_primary:
        StdCurriEnroll.objects.filter(
            student_id=target_row.student_id,
            is_primary=True,
        ).exclude(pk=target_row.pk).update(is_primary=False)
    if update_fields:
        target_row.save(update_fields=update_fields)
    source_row.delete()
    return True, summary


def reconcile_std_curri_records(
    student: Student,
    target_curriculum: Curriculum,
    source_curriculum: Curriculum,
) -> StdCurriRecordMergeSummaryT:
    """Reconcile one student's records between two curricula by matching courses."""
    summary = empty_std_curri_record_summary()

    target_curriculum_courses = list(
        CurriCrs.objects.filter(curriculum=target_curriculum)
        .select_related("course")
        .only("id", "course_id", "course__department_id", "course__number")
    )
    # > Match target/source rows by canonical course identity.
    target_cc_by_course_identity = _index_curri_crss_by_idity(target_curriculum_courses)
    if not target_cc_by_course_identity:
        return summary

    source_curriculum_courses = list(
        CurriCrs.objects.filter(curriculum=source_curriculum)
        .select_related("course")
        .only("id", "course_id", "course__department_id", "course__number")
    )
    source_course_identity_by_curriculum_course_id = _idity_by_curri_crs_id(
        source_curriculum_courses
    )
    source_curriculum_course_ids = [
        curriculum_course.id
        for curriculum_course in source_curriculum_courses
        if source_course_identity_by_curriculum_course_id.get(curriculum_course.id)
        in target_cc_by_course_identity
    ]
    if not source_curriculum_course_ids:
        return summary

    # Gather all section ids touched by the student once to avoid per-course joins.
    source_grade_by_section_id = {
        grade.section_id: grade
        for grade in Grade.objects.filter(
            student=student,
            section__curriculum_course_id__in=source_curriculum_course_ids,
        )
    }
    source_registration_by_section_id = {
        registration.section_id: registration
        for registration in Registration.objects.filter(
            student=student,
            section__curriculum_course_id__in=source_curriculum_course_ids,
        )
    }
    source_section_ids = set(source_grade_by_section_id).union(
        source_registration_by_section_id
    )
    if not source_section_ids:
        return summary

    source_sections = list(
        Section.objects.filter(id__in=source_section_ids)
        .only("id", "semester_id", "number", "curriculum_course_id")
        .order_by("curriculum_course_id", "semester_id", "number", "id")
    )
    source_semesters_by_target_curriculum_course_id: dict[int, set[int]] = defaultdict(
        set
    )
    for source_section in source_sections:
        source_course_identity = source_course_identity_by_curriculum_course_id.get(
            source_section.curriculum_course_id
        )
        if source_course_identity is None:
            continue
        target_curriculum_course = target_cc_by_course_identity.get(
            source_course_identity
        )
        if target_curriculum_course is None:
            continue
        source_semesters_by_target_curriculum_course_id[target_curriculum_course.id].add(
            source_section.semester_id
        )

    target_curriculum_course_ids = list(source_semesters_by_target_curriculum_course_id)
    if not target_curriculum_course_ids:
        return summary

    target_grade_values_by_course_identity: dict[CrsIdityT, set[int | None]] = (
        defaultdict(set)
    )
    for department_id, course_number, value_id in Grade.objects.filter(
        student=student,
        section__curriculum_course_id__in=target_curriculum_course_ids,
    ).values_list(
        "section__curriculum_course__course__department_id",
        "section__curriculum_course__course__number",
        "value_id",
    ):
        identity = _build_crs_idity(department_id, course_number)
        if identity is None:
            continue
        target_grade_values_by_course_identity[identity].add(value_id)
    target_has_grade_course_identities = set(target_grade_values_by_course_identity)

    target_registration_course_identities: set[CrsIdityT] = set()
    for department_id, course_number in Registration.objects.filter(
        student=student,
        section__curriculum_course_id__in=target_curriculum_course_ids,
    ).values_list(
        "section__curriculum_course__course__department_id",
        "section__curriculum_course__course__number",
    ):
        identity = _build_crs_idity(department_id, course_number)
        if identity is None:
            continue
        target_registration_course_identities.add(identity)

    target_sections_filter = Q(pk__in=[])
    for (
        target_curriculum_course_id,
        source_semester_ids,
    ) in source_semesters_by_target_curriculum_course_id.items():
        target_sections_filter |= Q(
            curriculum_course_id=target_curriculum_course_id,
            semester_id__in=source_semester_ids,
        )

    target_sections_by_curriculum_course_id: dict[int, list[Section]] = defaultdict(list)
    for section in Section.objects.filter(target_sections_filter).only(
        "id", "semester_id", "number", "curriculum_course_id"
    ):
        target_sections_by_curriculum_course_id[section.curriculum_course_id].append(
            section
        )
    indexed_target_sections: dict[
        int, tuple[dict[tuple[int, int], Section], dict[int, list[Section]]]
    ] = {}
    for (
        target_curriculum_course_id,
        sections,
    ) in target_sections_by_curriculum_course_id.items():
        indexed_target_sections[target_curriculum_course_id] = (
            _index_sec_merge_candidates(sections)
        )

    for source_section in source_sections:
        source_course_identity = source_course_identity_by_curriculum_course_id.get(
            source_section.curriculum_course_id
        )
        if source_course_identity is None:
            continue
        target_cc = target_cc_by_course_identity.get(source_course_identity)
        if target_cc is None:
            continue

        target_section: Section | None = None
        indexed_sections = indexed_target_sections.get(target_cc.id)
        if indexed_sections is not None:
            by_semester_number, by_semester = indexed_sections
            target_section = _pick_sec_merge_candidate_from_index(
                source_section,
                by_semester_number,
                by_semester,
            )

        source_grade = source_grade_by_section_id.get(source_section.id)
        if source_grade is not None:
            target_grade_values = target_grade_values_by_course_identity.get(
                source_course_identity, set()
            )
            # If same-value grade already exists on target curriculum/course, drop duplicate.
            if source_grade.value_id in target_grade_values:
                source_grade.delete()
                summary["grades_deduped"] += 1
            elif source_course_identity in target_has_grade_course_identities:
                # Conflicting values are left untouched for manual resolution.
                summary["grade_conflicts"] += 1
            elif target_section is not None:
                source_grade.section = target_section
                source_grade.save(update_fields=["section"])
                target_grade_values_by_course_identity[source_course_identity].add(
                    source_grade.value_id
                )
                target_has_grade_course_identities.add(source_course_identity)
                summary["grades_moved"] += 1
            else:
                summary["grades_unresolved"] += 1

        source_registration = source_registration_by_section_id.get(source_section.id)
        if source_registration is None:
            continue
        if source_course_identity in target_registration_course_identities:
            source_registration.delete()
            summary["registrations_deduped"] += 1
            continue
        if target_section is None:
            summary["registrations_unresolved"] += 1
            continue
        source_registration.section = target_section
        source_registration.save(update_fields=["section"])
        target_registration_course_identities.add(source_course_identity)
        summary["registrations_moved"] += 1
    return summary
