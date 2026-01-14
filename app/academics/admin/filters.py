"""Filters module."""

from __future__ import annotations

from typing import Sequence

from admin_searchable_dropdown.filters import (
    AutocompleteFilter,
    AutocompleteFilterFactory,
    _get_rel_model,
)
from django.contrib import admin
from django.db.models import Count, Model, QuerySet
from django.http import HttpRequest
from django.urls import reverse
from django_admin_filters import MultiChoice

from app.academics.models.curriculum import Curriculum
from app.academics.models.department import Department
from app.people.models.faculty import Faculty
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


class CurriculumCourseFacultyFilterAC(ScopedAutocompleteFilter):
    """Autocomplete filter constrained to faculty teaching curriculum courses."""

    title = "Faculty"
    parameter_name = "sections__faculty"
    field_name = "faculty"
    lookup_map: LookUpType = (("sections", "sections__faculty"),)
    target_model = Faculty
