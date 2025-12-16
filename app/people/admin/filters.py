"""Admin list filters for people app."""

from admin_searchable_dropdown.filters import AutocompleteFilterFactory
from app.shared.admin.filters import (
    BaseCollegeFilter,
    BaseDepartmentFilter,
    CurriculumByCollegeFilter,
)

StudentCurriculumFAC = AutocompleteFilterFactory("Curriculum", "curriculum")
StudentEntrySemFAC = AutocompleteFilterFactory("Entry Semester", "entry_semester")

FacultyDepartmentFAC = AutocompleteFilterFactory(
    "Department", "staff_profile__department"
)
FacultyGroupFAC = AutocompleteFilterFactory("Group", "staff_profile__user__groups")


