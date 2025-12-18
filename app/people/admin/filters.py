"""Admin list filters for people app."""

from admin_searchable_dropdown.filters import AutocompleteFilterFactory

from app.academics.admin.filters import CurriculumFilterAC
from app.shared.admin.filters import BaseCollegeFilter

StudentEntrySemFAC = AutocompleteFilterFactory("Entry Semester", "entry_semester")
FacultyGroupFAC = AutocompleteFilterFactory("Group", "staff_profile__user__groups")
