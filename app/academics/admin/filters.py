"""Filters module."""

from __future__ import annotations

from typing import Sequence

from admin_searchable_dropdown.filters import AutocompleteFilter
from django.contrib import admin

from app.academics.models.curriculum import Curriculum
from app.academics.models.department import Department
from app.people.models.faculty import Faculty
from app.people.models.student import Student
from app.shared.admin.filters import BaseCollegeFilter, ScopedAutocompleteFilter
from app.shared.types import LookUpType

DEPARTMENT_FIELD_LOOKUPS: LookUpType = (
    ("department", "department"),
    ("course", "course__department"),
    ("staff_profile", "staff_profile__department"),
    ("curriculum_course", "curriculum_course__course__department"),
)

CURRICULUM_FIELD_LOOKUPS: LookUpType = (
    ("curriculum", "curriculum"),
    ("curriculum_course", "curriculum_course__curriculum"),
    ("curricula", "curricula"),
    ("in_curriculum_courses", "in_curriculum_courses__curriculum"),
)

DEPARTMENT_CURRICULUM_LOOKUPS: LookUpType = (
    ("courses", "courses__in_curriculum_courses__curriculum"),
)


class CourseCollegeFilter(BaseCollegeFilter):
    field_path = "department__college"
    parameter_name = "department__college"


class DepartmentFilterAC(ScopedAutocompleteFilter):
    """Autocomplete filter constrained to departments present in the queryset."""

    title = "Department"
    parameter_name = "department"
    field_name = "department"
    lookup_map = DEPARTMENT_FIELD_LOOKUPS
    target_model = Department


class CurriculumFilterAC(ScopedAutocompleteFilter):
    """Autocomplete filter constrained to curricula present in the queryset."""

    title = "Curriculum"
    parameter_name = "curriculum"
    field_name = "curriculum"
    lookup_map = CURRICULUM_FIELD_LOOKUPS
    target_model = Curriculum


class DepartmentCurriculumFilterAC(ScopedAutocompleteFilter):
    """Autocomplete filter for curricula linked through department courses."""

    title = "Curriculum"
    parameter_name = "curriculum"
    field_name = "curriculum"
    lookup_map = DEPARTMENT_CURRICULUM_LOOKUPS
    target_model = Curriculum


class CourseCurriculumFilter(admin.SimpleListFilter):
    """Curriculum filter for courses (avoids reverse M2M autocomplete errors)."""

    title = "By Curriculum"
    parameter_name = "curricula__id__exact"

    def lookups(self, request, model_admin):
        curricula = Curriculum.objects.order_by("short_name").values_list(
            "id", "short_name"
        )
        return list(curricula)

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(curricula__id=self.value())
        return queryset


class CurriculumCourseFacultyFilterAC(ScopedAutocompleteFilter):
    """Autocomplete filter constrained to faculty teaching curriculum courses."""

    title = "Faculty"
    parameter_name = "sections__faculty"
    field_name = "faculty"
    lookup_map: LookUpType = (("sections", "sections__faculty"),)
    target_model = Faculty


class CurriculumCourseStudentFilterAC(ScopedAutocompleteFilter):
    """Autocomplete filter constrained to students registered in course sections."""

    title = "Student"
    parameter_name = "sections__section_registrations__student"
    field_name = "student"
    lookup_map: LookUpType = (("sections", "sections__section_registrations__student"),)
    target_model = Student
