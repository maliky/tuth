"""Module with the merging function for academic objects."""

from typing import TYPE_CHECKING

from django.contrib import admin, messages
from django.db import transaction

from app.academics.models.course import Course, CurriculumCourse
from app.academics.models.curriculum import Curriculum
from app.academics.models.department import Department
from app.people.models.student import Student

if TYPE_CHECKING:
    from app.academics.admin.core import CurriculumAdmin, DepartmentAdmin


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
        f"Merged {queryset.count() - 1} department(s) into {target.short_name}.",
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
