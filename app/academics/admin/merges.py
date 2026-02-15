"""Module with the merging function for academic objects."""

from typing import TYPE_CHECKING, Literal, TypeAlias, cast, no_type_check
from collections import defaultdict

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Count, Q
from django.db.models.deletion import ProtectedError

from app.academics.models.course import Course
from app.academics.models.curriculum_course import CurriCourse
from app.academics.models.curriculum import Curriculum
from app.academics.models.prerequisite import Prerequisite
from app.academics.models.concentration import Major, Minor
from app.academics.models.department import Department
from app.academics.models.concentration import (
    MajorCurriCourse,
    MinorCurriCourse,
)
from app.finance.models.invoice import Invoice
from app.people.models import RoleAssignment, Staff
from app.people.models.student import Student
from app.people.models.student_curriculum_enrollment import StdCurriEnroll
from app.registry.models.grade import Grade
from app.registry.models.registration import Registration
from app.timetable.models.section import Section

if TYPE_CHECKING:
    from app.academics.admin.core import CurriAdmin, DepartmentAdmin
    from app.academics.admin.core import CourseAdmin

CourseMergeSummaryT: TypeAlias = dict[str, int]
ConflictChoiceT = Literal["keep_target", "keep_source", "merge", "skip"]
ConflictChoiceByCourseIdT: TypeAlias = dict[int, ConflictChoiceT]
ConflictCurriCoursePairT: TypeAlias = tuple[CurriCourse, CurriCourse]
SectionMergeResultT: TypeAlias = dict[str, int]
StdCurriRecordMergeSummaryT: TypeAlias = dict[str, int]

MERGE_CHOICE_KEEP_TARGET: ConflictChoiceT = "keep_target"
MERGE_CHOICE_KEEP_SOURCE: ConflictChoiceT = "keep_source"
MERGE_CHOICE_MERGE: ConflictChoiceT = "merge"
MERGE_CHOICE_SKIP: ConflictChoiceT = "skip"


def empty_student_curriculum_record_summary() -> StdCurriRecordMergeSummaryT:
    """Return the default counters for student-scoped curriculum reconciliation."""
    return {
        "grades_moved": 0,
        "grades_deduped": 0,
        "grade_conflicts": 0,
        "grades_unresolved": 0,
        "registrations_moved": 0,
        "registrations_deduped": 0,
        "registrations_unresolved": 0,
    }


@admin.action(description="Merge selected departments into the first")
def merge_departments_action(dept_admin: "DepartmentAdmin", request, queryset):
    """Merge departments and summarize potential collisions.

    Args:
        dept_admin: Django admin instance.
        request: Current request.
        queryset: Selected department queryset.
    """
    if queryset.count() < 2:
        messages.warning(request, "Select at least two departments to merge.")
        return
    target = queryset.order_by("id").first()
    sources = queryset.exclude(pk=target.pk)
    collision_summary = _department_merge_collision_summary(target, sources)
    if collision_summary["course_number_collisions"]:
        messages.warning(
            request,
            (
                "Potential course number collisions detected: "
                f"{collision_summary['course_number_collisions']} number(s). "
                "Run scripts/department_merge_conflicts.sql for details."
            ),
        )
    if collision_summary["source_course_count"]:
        messages.info(
            request,
            (
                f"Source departments include {collision_summary['source_course_count']} "
                "course(s), "
                f"{collision_summary['source_staff_count']} staff profile(s), and "
                f"{collision_summary['source_role_count']} role assignment(s)."
            ),
        )
    summary = merge_departments(target, sources)
    messages.success(
        request,
        f"Merged {summary['merged']} department(s) into {target.shortname}.",
    )


@admin.action(description="Merge selected curricula into the chosen target")
def merge_curricula_action(curriculum_admin: "CurriAdmin", request, queryset):
    """Merge curricula, moving students and programmed courses into the target."""
    if queryset.count() < 2:
        messages.warning(request, "Select at least two curricula to merge.")
        return
    # Action form supplies the explicit target to avoid relying on selection order.
    target_id = request.POST.get("merge_target")
    if not target_id:
        messages.error(request, "Select a merge target before running this action.")
        return
    target = Curriculum.objects.filter(pk=target_id).first()
    if not target:
        messages.error(request, "Merge target curriculum was not found.")
        return
    if not queryset.filter(pk=target.pk).exists():
        messages.error(request, "Merge target must be part of the selection.")
        return
    sources = queryset.exclude(pk=target.pk)
    try:
        summary = merge_curricula(target, sources)
    except ValidationError as exc:
        messages.error(request, str(exc))
        return
    messages.success(
        request,
        f"Merged {summary['curricula_merged']} curriculum/curricula into "
        f"{target.short_name}.",
    )
    if summary["curricula_retained"]:
        messages.warning(
            request,
            (
                "Some source curricula were retained due to invoice conflicts. "
                "Run scripts/curriculum_merge_conflicts.sql before retrying."
            ),
        )
    if summary["sections_merged"]:
        messages.warning(
            request,
            f"Merged {summary['sections_merged']} conflicting section(s).",
        )
    if summary["prerequisites_skipped"]:
        messages.warning(
            request,
            f"Skipped {summary['prerequisites_skipped']} duplicate prerequisite(s).",
        )
    if summary["skipped_invoices"]:
        messages.warning(
            request,
            f"Skipped {summary['skipped_invoices']} curriculum course(s) with invoices.",
        )
    if summary["credit_hours_conflicts"]:
        messages.warning(
            request,
            (
                "Credit hours differ on "
                f"{summary['credit_hours_conflicts']} curriculum course(s)."
            ),
        )
    if summary["is_required_conflicts"]:
        messages.warning(
            request,
            (
                "Required flag differs on "
                f"{summary['is_required_conflicts']} curriculum course(s)."
            ),
        )
    if summary["is_elective_conflicts"]:
        messages.warning(
            request,
            (
                "Elective flag differs on "
                f"{summary['is_elective_conflicts']} curriculum course(s)."
            ),
        )
    if summary["sections_skipped_grade_conflict"]:
        messages.warning(
            request,
            (
                "Skipped "
                f"{summary['sections_skipped_grade_conflict']} section merge(s) "
                "because overlapping students had different grade values."
            ),
        )
    if summary["sections_retained_protected"]:
        messages.warning(
            request,
            (
                "Retained "
                f"{summary['sections_retained_protected']} conflicting section(s) "
                "because grades still protect them."
            ),
        )
    if summary["protected_deletes"]:
        messages.warning(
            request,
            (
                "Could not delete "
                f"{summary['protected_deletes']} source object(s) because grades "
                "protect related sections."
            ),
        )


def list_curriculum_course_conflicts(
    target: Curriculum, source: Curriculum
) -> tuple[list[ConflictCurriCoursePairT], list[CurriCourse]]:
    """Return conflicting and non-conflicting programmed courses for two curricula."""
    target_rows = CurriCourse.objects.filter(curriculum=target).select_related(
        "course",
        "credit_hours",
    )
    source_rows = CurriCourse.objects.filter(curriculum=source).select_related(
        "course",
        "credit_hours",
    )
    target_by_course_id = {row.course_id: row for row in target_rows}
    conflicts: list[ConflictCurriCoursePairT] = []
    non_conflicting: list[CurriCourse] = []
    for source_row in source_rows:
        target_row = target_by_course_id.get(source_row.course_id)
        if target_row is None:
            non_conflicting.append(source_row)
            continue
        conflicts.append((target_row, source_row))
    return conflicts, non_conflicting


def _overlay_curriculum_course_fields(target: CurriCourse, source: CurriCourse) -> None:
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


def _keep_target_curriculum_course(
    target: CurriCourse, source: CurriCourse
) -> dict[str, int]:
    """Keep target programmed course and delete source when possible."""
    summary = {
        "sections_moved": 0,
        "sections_merged": 0,
        "sections_retained_protected": 0,
        "sections_skipped_grade_conflict": 0,
        "source_retained_protected": 0,
    }
    _merge_curriculum_course_links(target, source)
    try:
        source.delete()
    except ProtectedError:
        summary["source_retained_protected"] = 1
    return summary


def _merge_curriculum_course_conflict(
    target: CurriCourse,
    source: CurriCourse,
    choice: ConflictChoiceT,
) -> dict[str, int]:
    """Resolve one conflicting programmed course pair with a caller-selected mode."""
    if choice == MERGE_CHOICE_SKIP:
        return {
            "sections_moved": 0,
            "sections_merged": 0,
            "sections_retained_protected": 0,
            "sections_skipped_grade_conflict": 0,
            "source_retained_protected": 0,
        }
    if choice == MERGE_CHOICE_KEEP_SOURCE:
        # Keep the target row id for FK stability, while applying source metadata.
        _overlay_curriculum_course_fields(target, source)
        return _merge_curriculum_course_to_target(target, source)
    if choice == MERGE_CHOICE_KEEP_TARGET:
        return _keep_target_curriculum_course(target, source)
    return _merge_curriculum_course_to_target(target, source)


@transaction.atomic
def merge_curricula(
    target: Curriculum,
    sources,
    conflict_choices: ConflictChoiceByCourseIdT | None = None,
):
    """Merge curricula: move attached records to the target curriculum."""
    selected_choices: ConflictChoiceByCourseIdT = conflict_choices or {}
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
        moved_students = Student.objects.filter(curriculum=src).update(curriculum=target)
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
        for cc in CurriCourse.objects.filter(curriculum=src):
            # Avoid duplicate course entries on the target curriculum.
            existing = CurriCourse.objects.filter(
                curriculum=target, course=cc.course
            ).first()
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
                moved = _merge_curriculum_course_conflict(
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


@transaction.atomic
def merge_departments(target: Department, sources):
    """Merge departments by reassigning dependent records to the target.

    Args:
        target: Department to keep.
        sources: Departments to merge into the target.

    Returns:
        dict[str, int]: Summary counts for updated records.
    """
    summary = {
        "merged": 0,
        "courses_moved": 0,
        "course_codes_rebuilt": 0,
        "staff_moved": 0,
        "roles_moved": 0,
    }
    for src in sources:
        if src.pk == target.pk:
            continue
        courses = list(Course.objects.filter(department=src))
        for course in courses:
            course.department = target
            course.code = ""
            course.short_code = ""
            course.save(update_fields=["department", "code", "short_code"])
        summary["courses_moved"] += len(courses)
        summary["course_codes_rebuilt"] += len(courses)
        summary["staff_moved"] += Staff.objects.filter(department=src).update(
            department=target
        )
        summary["roles_moved"] += RoleAssignment.objects.filter(department=src).update(
            department=target
        )
        Department.objects.filter(pk=src.pk).delete()
        summary["merged"] += 1
    return summary


# Avoid mypy internal error on the annotate chain for collision summaries.
@no_type_check
def _department_merge_collision_summary(target: Department, sources) -> dict[str, int]:
    """Summarize potential department merge collisions.

    Args:
        target: Department to keep.
        sources: Departments to merge into the target.

    Returns:
        dict[str, int]: Counts of potential collisions and affected records.
    """
    source_ids = [dept.pk for dept in sources if dept.pk]
    if not target.pk or not source_ids:
        return {
            "course_number_collisions": 0,
            "source_course_count": 0,
            "source_staff_count": 0,
            "source_role_count": 0,
        }
    dept_ids = [target.pk] + source_ids
    collisions = (
        Course.objects.filter(department_id__in=dept_ids)
        .values("number")
        .annotate(course_count=Count("id"))
        .filter(course_count__gt=1)
    )
    return {
        "course_number_collisions": collisions.count(),
        "source_course_count": Course.objects.filter(
            department_id__in=source_ids
        ).count(),
        "source_staff_count": Staff.objects.filter(department_id__in=source_ids).count(),
        "source_role_count": RoleAssignment.objects.filter(
            department_id__in=source_ids
        ).count(),
    }


@admin.action(description="Merge selected courses into the first")
def merge_courses_action(course_admin: "CourseAdmin", request, queryset):
    """Merge courses: move curriculum-course links and sections to the first course."""
    if queryset.count() < 2:
        messages.warning(request, "Select at least two courses to merge.")
        return
    target = queryset.order_by("id").first()
    sources = queryset.exclude(pk=target.pk)
    summary = merge_courses(target, sources)
    messages.success(
        request,
        f"Merged {summary['merged']} course(s) into {target.short_code}.",
    )
    if summary["skipped_invoices"]:
        messages.warning(
            request,
            f"Skipped {summary['skipped_invoices']} course(s) with invoice conflicts.",
        )
    if summary["prerequisites_skipped"]:
        messages.info(
            request,
            f"Skipped {summary['prerequisites_skipped']} prerequisite row(s).",
        )
    if summary["sections_skipped_grade_conflict"]:
        messages.warning(
            request,
            (
                "Skipped "
                f"{summary['sections_skipped_grade_conflict']} section merge(s) "
                "because overlapping students had different grade values."
            ),
        )
    if summary["sections_retained_protected"]:
        messages.warning(
            request,
            (
                "Retained "
                f"{summary['sections_retained_protected']} conflicting section(s) "
                "because grades still protect them."
            ),
        )
    if summary["protected_deletes"]:
        messages.warning(
            request,
            (
                "Could not delete "
                f"{summary['protected_deletes']} source course(s) because grades "
                "protect related sections."
            ),
        )


def _select_course_merge_target(courses: list[Course]) -> Course:
    """Pick a target course based on description or smallest id."""
    # Prefer the course with a description, otherwise default to the smallest id.
    with_description = [
        course for course in courses if course.description and course.description.strip()
    ]
    candidates = with_description or courses
    sorted_candidates = sorted(candidates, key=lambda course: course.id or 0)[0]
    # problem if no course has a descriptionthis will be empty.
    return sorted_candidates


@admin.action(description="Merge courses by short code")
def merge_courses_by_short_code_action(
    course_admin: "CourseAdmin",
    request,
    queryset,
):
    """Merge courses that share a short_code within the selection."""
    courses = list(queryset)
    if len(courses) < 2:
        messages.warning(request, "Select at least two courses to merge.")
        return

    grouped = defaultdict(list)
    for course in courses:
        if course.short_code:
            grouped[course.short_code].append(course)

    summary: CourseMergeSummaryT = {
        "groups": 0,
        "merged": 0,
        "skipped_invoices": 0,
        "prerequisites_skipped": 0,
        "sections_retained_protected": 0,
        "sections_skipped_grade_conflict": 0,
        "protected_deletes": 0,
    }
    for _short_code, items in grouped.items():
        if len(items) < 2:
            continue
        summary["groups"] += 1
        target = _select_course_merge_target(items)
        sources = [course for course in items if course.id != target.id]
        group_summary = merge_courses(target, sources)
        summary["merged"] += group_summary["merged"]
        summary["skipped_invoices"] += group_summary["skipped_invoices"]
        summary["prerequisites_skipped"] += group_summary["prerequisites_skipped"]
        summary["sections_retained_protected"] += group_summary[
            "sections_retained_protected"
        ]
        summary["sections_skipped_grade_conflict"] += group_summary[
            "sections_skipped_grade_conflict"
        ]
        summary["protected_deletes"] += group_summary["protected_deletes"]

    if summary["groups"] == 0:
        messages.info(request, "No duplicate short codes found in the selection.")
        return
    messages.success(
        request,
        (
            f"Merged {summary['merged']} course(s) across "
            f"{summary['groups']} short code group(s)."
        ),
    )
    if summary["skipped_invoices"]:
        messages.warning(
            request,
            f"Skipped {summary['skipped_invoices']} course(s) with invoice conflicts.",
        )
    if summary["prerequisites_skipped"]:
        messages.info(
            request,
            f"Skipped {summary['prerequisites_skipped']} prerequisite row(s).",
        )
    if summary["sections_skipped_grade_conflict"]:
        messages.warning(
            request,
            (
                "Skipped "
                f"{summary['sections_skipped_grade_conflict']} section merge(s) "
                "because overlapping students had different grade values."
            ),
        )
    if summary["sections_retained_protected"]:
        messages.warning(
            request,
            (
                "Retained "
                f"{summary['sections_retained_protected']} conflicting section(s) "
                "because grades still protect them."
            ),
        )
    if summary["protected_deletes"]:
        messages.warning(
            request,
            (
                "Could not delete "
                f"{summary['protected_deletes']} source course(s) because grades "
                "protect related sections."
            ),
        )


@transaction.atomic
def merge_courses(target: Course, sources):
    """Merge source courses into the target course.

    Args:
        target: Course to keep.
        sources: Iterable of source courses to merge into the target.

    Returns:
        dict[str, int]: Summary counts for merged and skipped records.
    """
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
        if _course_merge_has_invoice_conflict(source_curriculum_courses, target_cc_map):
            summary["skipped_invoices"] += 1
            continue
        # Merge or move curriculum courses before deleting the source course.
        for cc in source_curriculum_courses:
            curriculum_id = cc.curriculum_id
            existing = target_cc_map.get(curriculum_id)
            if existing:
                moved = _merge_curriculum_course_to_target(existing, cc)
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
        prereq_summary = _merge_course_prerequisites(target, src)
        summary["prerequisites_moved"] += prereq_summary["prerequisites_moved"]
        summary["prerequisites_skipped"] += prereq_summary["prerequisites_skipped"]
        try:
            src.delete()
        except ProtectedError:
            summary["protected_deletes"] += 1
            continue
        summary["merged"] += 1
    return summary


def _course_merge_has_invoice_conflict(
    source_curriculum_courses: list[CurriCourse],
    target_cc_map: dict[int, CurriCourse],
) -> bool:
    """Return True when invoices block merging source curriculum courses.

    Args:
        source_curriculum_courses: Curriculum courses attached to the source.
        target_cc_map: Lookup of target curriculum courses by curriculum id.

    Returns:
        bool: True if invoices exist on a conflicting curriculum course.
    """
    conflict_ids = [
        cc.id for cc in source_curriculum_courses if cc.curriculum_id in target_cc_map
    ]
    if not conflict_ids:
        return False
    return Invoice.objects.filter(curriculum_course_id__in=conflict_ids).exists()


def _merge_course_prerequisites(target: Course, source: Course) -> dict[str, int]:
    """Reassign prerequisite rows from the source course to the target course.

    Args:
        target: Course receiving prerequisite edges.
        source: Course being merged into the target.

    Returns:
        dict[str, int]: Counts of moved and skipped prerequisites.
    """
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


@admin.action(description="Merge selected curriculum courses into the first")
def merge_curriculum_courses_action(course_admin, request, queryset):
    """Merge curriculum courses with conflict checks and summary messages."""
    if queryset.count() < 2:
        messages.warning(request, "Select at least two curriculum courses to merge.")
        return
    target = queryset.order_by("id").first()
    sources = queryset.exclude(pk=target.pk)
    summary = merge_curriculum_courses(target, sources)
    messages.success(
        request,
        f"Merged {summary['merged']} curriculum course(s) into {target}.",
    )
    if summary["skipped_incompatible"]:
        messages.warning(
            request,
            f"Skipped {summary['skipped_incompatible']} incompatible selection(s).",
        )
    if summary["skipped_invoices"]:
        messages.warning(
            request,
            f"Skipped {summary['skipped_invoices']} curriculum course(s) with invoices.",
        )
    if summary["sections_merged"]:
        messages.info(
            request,
            f"Merged {summary['sections_merged']} conflicting section(s).",
        )
    if summary["credit_hours_conflicts"]:
        messages.warning(
            request,
            (
                "Credit hours differ on "
                f"{summary['credit_hours_conflicts']} selection(s)."
            ),
        )
    if summary["is_required_conflicts"]:
        messages.warning(
            request,
            (
                "Required flag differs on "
                f"{summary['is_required_conflicts']} selection(s)."
            ),
        )
    if summary["is_elective_conflicts"]:
        messages.warning(
            request,
            (
                "Elective flag differs on "
                f"{summary['is_elective_conflicts']} selection(s)."
            ),
        )
    if summary["sections_skipped_grade_conflict"]:
        messages.warning(
            request,
            (
                "Skipped "
                f"{summary['sections_skipped_grade_conflict']} section merge(s) "
                "because overlapping students had different grade values."
            ),
        )
    if summary["sections_retained_protected"]:
        messages.warning(
            request,
            (
                "Retained "
                f"{summary['sections_retained_protected']} conflicting section(s) "
                "because grades still protect them."
            ),
        )
    if summary["protected_deletes"]:
        messages.warning(
            request,
            (
                "Could not delete "
                f"{summary['protected_deletes']} source programmed course(s) "
                "because grades protect related sections."
            ),
        )


@transaction.atomic
def merge_curriculum_courses(target: CurriCourse, sources):
    """Merge CurriCourse rows into target.

    Rules:
    - Only merge rows with the same curriculum and course.
    - Section conflicts are merged into the target section.
    - Invoice conflicts keep the target; sources with invoices are skipped.
    - Concentration links move to the target when missing.
    """
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
        _merge_curriculum_course_links(target, src)
        source_sections = Section.objects.filter(curriculum_course=src)
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
            src.delete()
        except ProtectedError:
            summary["protected_deletes"] += 1
            continue
        summary["merged"] += 1
    return summary


def _merge_curriculum_course_links(target: CurriCourse, source: CurriCourse) -> None:
    """Move concentration links from a source curriculum course to the target."""
    for major_link in MajorCurriCourse.objects.filter(curriculum_course=source):
        if MajorCurriCourse.objects.filter(
            major_id=major_link.major_id, curriculum_course=target
        ).exists():
            continue
        major_link.curriculum_course = target
        major_link.save(update_fields=["curriculum_course"])
    for minor_link in MinorCurriCourse.objects.filter(curriculum_course=source):
        if MinorCurriCourse.objects.filter(
            minor_id=minor_link.minor_id, curriculum_course=target
        ).exists():
            continue
        minor_link.curriculum_course = target
        minor_link.save(update_fields=["curriculum_course"])


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
    """Merge a conflicting section into target, moving related records.

    Scope note:
        This is a section-wide merge used by global curriculum/course merges.
        It can move grades/registrations for multiple students in one call.

    Returns:
        SectionMergeResultT: Merge outcome counters keyed by result type.
    """
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


def _entry_semester_merge_blocked(
    target_row: StdCurriEnroll,
    source_row: StdCurriEnroll,
) -> bool:
    """Return True when both rows have different non-null entry semesters."""
    target_entry_id = target_row.entry_semester_id
    source_entry_id = source_row.entry_semester_id
    return bool(
        target_entry_id and source_entry_id and target_entry_id != source_entry_id
    )


def merge_student_enrollment_pair(
    target_row: StdCurriEnroll,
    source_row: StdCurriEnroll,
) -> tuple[bool, StdCurriRecordMergeSummaryT]:
    """Merge one source enrollment row into a target enrollment row.

    Scope note:
        This helper is student-scoped and intentionally does not call section-wide
        merges, because enrollment actions must not move records for other students.
    """
    summary = empty_student_curriculum_record_summary()
    if target_row.student_id != source_row.student_id:
        return False, summary
    if _entry_semester_merge_blocked(target_row, source_row):
        return False, summary

    # Reconcile student-scoped grade/registration duplicates before row collapse.
    summary = reconcile_student_curriculum_records(
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


def reconcile_student_curriculum_records(
    student: Student,
    target_curriculum: Curriculum,
    source_curriculum: Curriculum,
) -> StdCurriRecordMergeSummaryT:
    """Reconcile one student's records between two curricula by matching courses.

    The function is intentionally student-scoped: it never merges whole sections,
    and only moves/de-duplicates this student's grade/registration rows.
    Global curriculum merges use section-wide helpers for batch performance.
    """
    summary = empty_student_curriculum_record_summary()

    target_curriculum_courses = list(
        CurriCourse.objects.filter(curriculum=target_curriculum).only("id", "course_id")
    )
    target_cc_by_course_id = {
        curriculum_course.course_id: curriculum_course
        for curriculum_course in target_curriculum_courses
    }
    if not target_cc_by_course_id:
        return summary

    source_curriculum_courses = list(
        CurriCourse.objects.filter(curriculum=source_curriculum).only("id", "course_id")
    )
    source_course_id_by_curriculum_course_id = {
        curriculum_course.id: curriculum_course.course_id
        for curriculum_course in source_curriculum_courses
    }
    source_curriculum_course_ids = [
        curriculum_course.id
        for curriculum_course in source_curriculum_courses
        if curriculum_course.course_id in target_cc_by_course_id
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
        source_course_id = source_course_id_by_curriculum_course_id.get(
            source_section.curriculum_course_id
        )
        if source_course_id is None:
            continue
        target_curriculum_course = target_cc_by_course_id.get(source_course_id)
        if target_curriculum_course is None:
            continue
        source_semesters_by_target_curriculum_course_id[
            target_curriculum_course.id
        ].add(source_section.semester_id)

    target_curriculum_course_ids = list(source_semesters_by_target_curriculum_course_id)
    if not target_curriculum_course_ids:
        return summary

    target_grade_values_by_course_id: dict[int, set[int | None]] = defaultdict(set)
    for course_id, value_id in Grade.objects.filter(
        student=student,
        section__curriculum_course_id__in=target_curriculum_course_ids,
    ).values_list("section__curriculum_course__course_id", "value_id"):
        target_grade_values_by_course_id[course_id].add(value_id)
    target_has_grade_course_ids = set(target_grade_values_by_course_id)

    target_registration_course_ids = set(
        Registration.objects.filter(
            student=student,
            section__curriculum_course_id__in=target_curriculum_course_ids,
        ).values_list("section__curriculum_course__course_id", flat=True)
    )

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
            _index_section_merge_candidates(sections)
        )

    for source_section in source_sections:
        source_course_id = source_course_id_by_curriculum_course_id.get(
            source_section.curriculum_course_id
        )
        if source_course_id is None:
            continue
        target_cc = target_cc_by_course_id.get(source_course_id)
        if target_cc is None:
            continue

        target_section: Section | None = None
        indexed_sections = indexed_target_sections.get(target_cc.id)
        if indexed_sections is not None:
            by_semester_number, by_semester = indexed_sections
            target_section = _pick_section_merge_candidate_from_index(
                source_section,
                by_semester_number,
                by_semester,
            )

        source_grade = source_grade_by_section_id.get(source_section.id)
        if source_grade is not None:
            target_grade_values = target_grade_values_by_course_id.get(
                source_course_id, set()
            )
            # If same-value grade already exists on target curriculum/course, drop duplicate.
            if source_grade.value_id in target_grade_values:
                source_grade.delete()
                summary["grades_deduped"] += 1
            elif source_course_id in target_has_grade_course_ids:
                # Conflicting values are left untouched for manual resolution.
                summary["grade_conflicts"] += 1
            elif target_section is not None:
                source_grade.section = target_section
                source_grade.save(update_fields=["section"])
                target_grade_values_by_course_id[source_course_id].add(
                    source_grade.value_id
                )
                target_has_grade_course_ids.add(source_course_id)
                summary["grades_moved"] += 1
            else:
                summary["grades_unresolved"] += 1

        source_registration = source_registration_by_section_id.get(source_section.id)
        if source_registration is None:
            continue
        if source_course_id in target_registration_course_ids:
            source_registration.delete()
            summary["registrations_deduped"] += 1
            continue
        if target_section is None:
            summary["registrations_unresolved"] += 1
            continue
        source_registration.section = target_section
        source_registration.save(update_fields=["section"])
        target_registration_course_ids.add(source_course_id)
        summary["registrations_moved"] += 1
    return summary
