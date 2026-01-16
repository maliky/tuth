"""Module with the merging function for academic objects."""

from typing import TYPE_CHECKING

from django.contrib import admin, messages
from django.db import transaction

from app.academics.models.course import Course, CurriculumCourse
from app.academics.models.curriculum import Curriculum
from app.academics.models.department import Department
from app.academics.models.concentration import (
    MajorCurriculumCourse,
    MinorCurriculumCourse,
)
from app.finance.models.invoice import Invoice
from app.people.models.student import Student
from app.registry.models.grade import Grade
from app.registry.models.registration import Registration
from app.timetable.models.section import Section

if TYPE_CHECKING:
    from app.academics.admin.core import CurriculumAdmin, DepartmentAdmin
    from app.academics.admin.core import CourseAdmin


@admin.action(description="Merge selected departments into the first")
def merge_departments_action(dept_admin: "DepartmentAdmin", request, queryset):
    """Merge departments: move courses into the first selected department."""
    if queryset.count() < 2:
        messages.warning(request, "Select at least two departments to merge.")
        return
    target = queryset.order_by("id").first()
    merge_departments(target, queryset.exclude(pk=target.pk))
    messages.success(
        request,
        f"Merged {queryset.count() - 1} department(s) into {target.shortname}.",
    )


@admin.action(description="Merge selected curricula into the first")
def merge_curricula_action(curriculum_admin: "CurriculumAdmin", request, queryset):
    """Merge curricula, moving students and programmed courses into the first."""
    if queryset.count() < 2:
        messages.warning(request, "Select at least two curricula to merge.")
        return
    target = queryset.order_by("id").first()
    merge_curricula(target, queryset.exclude(pk=target.pk))
    messages.success(
        request,
        f"Merged {queryset.count() - 1} curricula into {target.short_name}.",
    )


@transaction.atomic
def merge_curricula(target: Curriculum, sources):
    """Merge curricula: move students and curriculum courses to target."""
    for src in sources:
        if src.pk == target.pk:
            continue
        Student.objects.filter(curriculum=src).update(curriculum=target)
        for cc in CurriculumCourse.objects.filter(curriculum=src):
            # Avoid duplicate course entries on the target curriculum
            existing = CurriculumCourse.objects.filter(
                curriculum=target, course=cc.course
            ).first()
            if existing:
                continue
            cc.curriculum = target
            cc.save()
        src.delete()


@transaction.atomic
def merge_departments(target: Department, sources):
    """Merge departments: move courses (and their curricula) to target."""
    for src in sources:
        if src.pk == target.pk:
            continue
        Course.objects.filter(department=src).update(department=target)
        Department.objects.filter(pk=src.pk).delete()


@admin.action(description="Merge selected courses into the first")
def merge_courses_action(course_admin: "CourseAdmin", request, queryset):
    """Merge courses: move curriculum-course links and sections to the first course."""
    if queryset.count() < 2:
        messages.warning(request, "Select at least two courses to merge.")
        return
    target = queryset.order_by("id").first()
    sources = queryset.exclude(pk=target.pk)
    merge_courses(target, sources)
    messages.success(
        request,
        f"Merged {sources.count()} course(s) into {target.short_code}.",
    )


@transaction.atomic
def merge_courses(target: Course, sources):
    """Move sections and curriculum links from sources to target."""
    for src in sources:
        if src.pk == target.pk:
            continue
        # Move sections
        Section.objects.filter(curriculum_course__course=src).update(
            curriculum_course__course=target
        )
        # Move curriculum-course links
        for cc in CurriculumCourse.objects.filter(course=src):
            existing = CurriculumCourse.objects.filter(
                course=target, curriculum=cc.curriculum
            ).first()
            if existing:
                continue
            cc.course = target
            cc.save()
        src.delete()


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


@transaction.atomic
def merge_curriculum_courses(target: CurriculumCourse, sources):
    """Merge CurriculumCourse rows into target.

    Rules:
    - Only merge rows with the same curriculum and course department.
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
    }
    for src in sources:
        if src.pk == target.pk:
            continue
        if src.curriculum_id != target.curriculum_id:
            summary["skipped_incompatible"] += 1
            continue
        if src.course.department_id != target.course.department_id:
            summary["skipped_incompatible"] += 1
            continue
        if Invoice.objects.filter(curriculum_course=src).exists():
            summary["skipped_invoices"] += 1
            continue
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
