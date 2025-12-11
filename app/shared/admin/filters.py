"""Shared admin filters (college/department/curriculum/level)."""

from __future__ import annotations

from typing import Iterable

from django.contrib import admin

from app.academics.choices import LEVEL_NUMBER
from app.academics.models.college import College
from app.academics.models.department import Department
from app.academics.models.curriculum import Curriculum
from app.people.models.student import Student


class BaseCollegeFilter(admin.SimpleListFilter):
    """Generic college filter with configurable field path."""

    title = "college"
    parameter_name = "college__id__exact"
    field_path = "college"

    def lookups(self, request, model_admin):
        colleges = College.objects.order_by("code").values_list("id", "code")
        return list(colleges)

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(**{f"{self.field_path}__id": self.value()})
        return queryset


class BaseDepartmentFilter(admin.SimpleListFilter):
    """Department filter that narrows choices by selected college."""

    title = "department"
    parameter_name = "department__id__exact"
    dept_field = "department"
    college_param = "college__id__exact"

    def lookups(self, request, model_admin):
        qs = Department.objects.select_related("college").order_by(
            "college__code", "short_name"
        )
        college_id = request.GET.get(self.college_param)
        if college_id:
            qs = qs.filter(college_id=college_id)
        return list(qs.values_list("id", "short_name"))

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(**{f"{self.dept_field}__id": self.value()})
        return queryset


class CurriculumByCollegeFilter(admin.SimpleListFilter):
    """Curriculum filter scoped by selected college."""

    title = "curriculum"
    parameter_name = "curriculum__id__exact"
    curriculum_field = "curriculum"
    college_param = "college__id__exact"

    def lookups(self, request, model_admin):
        qs = Curriculum.objects.select_related("college").order_by(
            "college__code", "short_name"
        )
        college_id = request.GET.get(self.college_param)
        if college_id:
            qs = qs.filter(college_id=college_id)
        return list(qs.values_list("id", "short_name"))

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(**{f"{self.curriculum_field}__id": self.value()})
        return queryset


class StudentLevelFilter(admin.SimpleListFilter):
    """Filter students by computed class level (credits-based)."""

    title = "level"
    parameter_name = "class_level"

    def lookups(self, request, model_admin):
        return [(lv.label, lv.label) for lv in LEVEL_NUMBER]

    def queryset(self, request, qs):
        level = self.value()
        if not level:
            return qs
        # Compute levels in Python; limited to current queryset ids.
        ids: list[int] = []
        for student in qs.select_related("curriculum"):
            if student.class_level == level:
                ids.append(student.id)
        return qs.filter(id__in=ids)
