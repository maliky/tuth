"""Module with the merging function for academic objects."""

from typing import TYPE_CHECKING, no_type_check

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q

from app.academics.models.course import Course, CurriculumCourse
from app.academics.models.curriculum import Curriculum
from app.academics.models.prerequisite import Prerequisite
from app.academics.models.concentration import Major, Minor
from app.academics.models.department import Department
from app.academics.models.concentration import (
    MajorCurriculumCourse,
    MinorCurriculumCourse,
)
from app.finance.models.invoice import Invoice
from app.people.models import RoleAssignment, Staff
from app.people.models.student import Student
from app.registry.models.grade import Grade
from app.registry.models.registration import Registration
from app.timetable.models.section import Section

if TYPE_CHECKING:
    from app.academics.admin.core import CurriculumAdmin, DepartmentAdmin
    from app.academics.admin.core import CourseAdmin


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
def merge_curricula_action(curriculum_admin: "CurriculumAdmin", request, queryset):
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


@transaction.atomic
def merge_curricula(target: Curriculum, sources):
    """Merge curricula: move attached records to the target curriculum."""
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
        for cc in CurriculumCourse.objects.filter(curriculum=src):
            # Avoid duplicate course entries on the target curriculum.
            existing = CurriculumCourse.objects.filter(
                curriculum=target, course=cc.course
            ).first()
            if existing:
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
                moved = _merge_curriculum_course_to_target(existing, cc)
                summary["sections_moved"] += moved["sections_moved"]
                summary["sections_merged"] += moved["sections_merged"]
                summary["curriculum_courses_merged"] += 1
                continue
            cc.curriculum = target
            cc.save(update_fields=["curriculum"])
            summary["curriculum_courses_moved"] += 1
        if skip_delete:
            summary["curricula_retained"] += 1
            continue
        src.delete()
        summary["curricula_merged"] += 1
    return summary


def _merge_curriculum_course_to_target(
    target: CurriculumCourse, source: CurriculumCourse
) -> dict[str, int]:
    """Move section and concentration links from source to target."""
    summary = {"sections_moved": 0, "sections_merged": 0}
    _merge_curriculum_course_links(target, source)
    source_sections = Section.objects.filter(curriculum_course=source)
    for section in source_sections:
        conflict = Section.objects.filter(
            curriculum_course=target,
            semester_id=section.semester_id,
            number=section.number,
        ).first()
        if conflict:
            _merge_sections(conflict, section)
            summary["sections_merged"] += 1
            continue
        section.curriculum_course = target
        section.save(update_fields=["curriculum_course"])
        summary["sections_moved"] += 1
    source.delete()
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
    }
    target_cc_map = {
        cc.curriculum_id: cc
        for cc in CurriculumCourse.objects.filter(course=target).select_related(
            "curriculum"
        )
    }
    for src in sources:
        if src.pk == target.pk:
            continue
        source_curriculum_courses = list(
            CurriculumCourse.objects.filter(course=src).select_related("curriculum")
        )
        if _course_merge_has_invoice_conflict(source_curriculum_courses, target_cc_map):
            summary["skipped_invoices"] += 1
            continue
        # > Merge or move curriculum courses before deleting the source course.
        for cc in source_curriculum_courses:
            curriculum_id = cc.curriculum_id
            existing = target_cc_map.get(curriculum_id)
            if existing:
                moved = _merge_curriculum_course_to_target(existing, cc)
                summary["sections_moved"] += moved["sections_moved"]
                summary["sections_merged"] += moved["sections_merged"]
                summary["curriculum_courses_merged"] += 1
                continue
            cc.course = target
            cc.save(update_fields=["course"])
            target_cc_map[curriculum_id] = cc
            summary["curriculum_courses_moved"] += 1
        prereq_summary = _merge_course_prerequisites(target, src)
        summary["prerequisites_moved"] += prereq_summary["prerequisites_moved"]
        summary["prerequisites_skipped"] += prereq_summary["prerequisites_skipped"]
        src.delete()
        summary["merged"] += 1
    return summary


def _course_merge_has_invoice_conflict(
    source_curriculum_courses: list[CurriculumCourse],
    target_cc_map: dict[int, CurriculumCourse],
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


@transaction.atomic
def merge_curriculum_courses(target: CurriculumCourse, sources):
    """Merge CurriculumCourse rows into target.

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
            conflict = Section.objects.filter(
                curriculum_course=target,
                semester_id=section.semester_id,
                number=section.number,
            ).first()
            if conflict:
                summary["sections_merged"] += 1
                _merge_sections(conflict, section)
                continue
            section.curriculum_course = target
            section.save(update_fields=["curriculum_course"])
            summary["sections_moved"] += 1
        src.delete()
        summary["merged"] += 1
    return summary


def _merge_curriculum_course_links(
    target: CurriculumCourse, source: CurriculumCourse
) -> None:
    """Move concentration links from a source curriculum course to the target."""
    for major_link in MajorCurriculumCourse.objects.filter(curriculum_course=source):
        if MajorCurriculumCourse.objects.filter(
            major_id=major_link.major_id, curriculum_course=target
        ).exists():
            continue
        major_link.curriculum_course = target
        major_link.save(update_fields=["curriculum_course"])
    for minor_link in MinorCurriculumCourse.objects.filter(curriculum_course=source):
        if MinorCurriculumCourse.objects.filter(
            minor_id=minor_link.minor_id, curriculum_course=target
        ).exists():
            continue
        minor_link.curriculum_course = target
        minor_link.save(update_fields=["curriculum_course"])


def _merge_sections(target: Section, source: Section) -> None:
    """Merge a conflicting section into target, moving related records."""
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

    source.delete()
