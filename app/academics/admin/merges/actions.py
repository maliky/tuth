"""Admin action entry points for academics merge operations."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from app.academics.models.course import Course
from app.academics.models.curriculum import Curriculum

from .course_merge import (
    _select_crs_merge_target,
    merge_crss,
    merge_curri_crss,
)
from .curriculum_merge import merge_curra
from .helpers import (
    CrsMergeSummaryT,
    _dpt_merge_collision_summary,
    merge_dpts,
)

if TYPE_CHECKING:
    from app.academics.admin.core import CrsAdmin, CurriAdmin, DptAdmin


@admin.action(description="Merge selected departments into the first")
def merge_dpts_action(dept_admin: "DptAdmin", request, queryset):
    """Merge departments and summarize potential collisions."""
    if queryset.count() < 2:
        messages.warning(request, "Select at least two departments to merge.")
        return
    target = queryset.order_by("id").first()
    sources = queryset.exclude(pk=target.pk)
    collision_summary = _dpt_merge_collision_summary(target, sources)
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
    summary = merge_dpts(target, sources)
    messages.success(
        request,
        f"Merged {summary['merged']} department(s) into {target.shortname}.",
    )


@admin.action(description="Merge selected curricula into the chosen target")
def merge_curra_action(curriculum_admin: "CurriAdmin", request, queryset):
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
        summary = merge_curra(target, sources)
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
    if summary["sections_rebucketed_sem0"]:
        messages.info(
            request,
            (
                "Rebucketed "
                f"{summary['sections_rebucketed_sem0']} sem0 section conflict(s) "
                "into semesters 1..3."
            ),
        )
    if summary["sections_blocked_sem0_overflow"]:
        messages.warning(
            request,
            (
                "Blocked "
                f"{summary['sections_blocked_sem0_overflow']} sem0 conflict(s) "
                "because no free semester slot (1..3) was available."
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


@admin.action(description="Merge selected courses into the first")
def merge_crss_action(course_admin: "CrsAdmin", request, queryset):
    """Merge courses: move curriculum-course links and sections to the first course."""
    if queryset.count() < 2:
        messages.warning(request, "Select at least two courses to merge.")
        return
    target = queryset.order_by("id").first()
    sources = queryset.exclude(pk=target.pk)
    summary = merge_crss(target, sources)
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
    if summary["sections_rebucketed_sem0"]:
        messages.info(
            request,
            (
                "Rebucketed "
                f"{summary['sections_rebucketed_sem0']} sem0 section conflict(s) "
                "into semesters 1..3."
            ),
        )
    if summary["sections_blocked_sem0_overflow"]:
        messages.warning(
            request,
            (
                "Blocked "
                f"{summary['sections_blocked_sem0_overflow']} sem0 conflict(s) "
                "because no free semester slot (1..3) was available."
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


@admin.action(description="Merge courses by short code")
def merge_crss_by_short_code_action(
    course_admin: "CrsAdmin",
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

    summary: CrsMergeSummaryT = {
        "groups": 0,
        "merged": 0,
        "skipped_invoices": 0,
        "prerequisites_skipped": 0,
        "sections_retained_protected": 0,
        "sections_skipped_grade_conflict": 0,
        "sections_rebucketed_sem0": 0,
        "sections_blocked_sem0_overflow": 0,
        "protected_deletes": 0,
    }
    for _short_code, items in grouped.items():
        if len(items) < 2:
            continue
        summary["groups"] += 1
        target = _select_crs_merge_target(items)
        sources = [course for course in items if course.id != target.id]
        group_summary = merge_crss(target, sources)
        summary["merged"] += group_summary["merged"]
        summary["skipped_invoices"] += group_summary["skipped_invoices"]
        summary["prerequisites_skipped"] += group_summary["prerequisites_skipped"]
        summary["sections_retained_protected"] += group_summary[
            "sections_retained_protected"
        ]
        summary["sections_skipped_grade_conflict"] += group_summary[
            "sections_skipped_grade_conflict"
        ]
        summary["sections_rebucketed_sem0"] += group_summary["sections_rebucketed_sem0"]
        summary["sections_blocked_sem0_overflow"] += group_summary[
            "sections_blocked_sem0_overflow"
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
    if summary["sections_rebucketed_sem0"]:
        messages.info(
            request,
            (
                "Rebucketed "
                f"{summary['sections_rebucketed_sem0']} sem0 section conflict(s) "
                "into semesters 1..3."
            ),
        )
    if summary["sections_blocked_sem0_overflow"]:
        messages.warning(
            request,
            (
                "Blocked "
                f"{summary['sections_blocked_sem0_overflow']} sem0 conflict(s) "
                "because no free semester slot (1..3) was available."
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


@admin.action(description="Merge selected curriculum courses into the first")
def merge_curri_crss_action(course_admin, request, queryset):
    """Merge curriculum courses with conflict checks and summary messages."""
    if queryset.count() < 2:
        messages.warning(request, "Select at least two curriculum courses to merge.")
        return
    target = queryset.order_by("id").first()
    sources = queryset.exclude(pk=target.pk)
    summary = merge_curri_crss(target, sources)
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
            (f"Credit hours differ on {summary['credit_hours_conflicts']} selection(s)."),
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
    if summary["sections_rebucketed_sem0"]:
        messages.info(
            request,
            (
                "Rebucketed "
                f"{summary['sections_rebucketed_sem0']} sem0 section conflict(s) "
                "into semesters 1..3."
            ),
        )
    if summary["sections_blocked_sem0_overflow"]:
        messages.warning(
            request,
            (
                "Blocked "
                f"{summary['sections_blocked_sem0_overflow']} sem0 conflict(s) "
                "because no free semester slot (1..3) was available."
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
