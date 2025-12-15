"""Admin list filters for people app."""

from admin_searchable_dropdown.filters import AutocompleteFilterFactory
from app.shared.admin.filters import (
    BaseCollegeFilter,
    BaseDepartmentFilter,
    CurriculumByCollegeFilter,
)


class StaffCollegeFilter(BaseCollegeFilter):
    field_path = "department__college"
    parameter_name = "department__college__id__exact"


class StaffDepartmentFilter(BaseDepartmentFilter):
    dept_field = "department"
    college_param = StaffCollegeFilter.parameter_name


class FacultyCollegeFilter(BaseCollegeFilter):
    field_path = "college"
    parameter_name = "college__id__exact"


class FacultyDepartmentFilter(BaseDepartmentFilter):
    dept_field = "staff_profile__department"
    college_param = FacultyCollegeFilter.parameter_name


class StudentCollegeFilter(BaseCollegeFilter):
    field_path = "curriculum__college"
    parameter_name = "curriculum__college__id__exact"


class StudentCurriculumFilter(CurriculumByCollegeFilter):
    curriculum_field = "curriculum"
    college_param = StudentCollegeFilter.parameter_name


FacultyDepartmentFilterAC = AutocompleteFilterFactory(
    "Department",
    "staff_profile__department",
)

FacultyGroupAC = AutocompleteFilterFactory(
    "Group",
    "staff_profile__user__groups",
)
