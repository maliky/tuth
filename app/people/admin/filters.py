"""Admin list filters for people app."""

from admin_searchable_dropdown.filters import AutocompleteFilterFactory

from app.academics.models.department import Department
from app.shared.admin.filters import ScopedAutocompleteFilter

StudentEntrySemFAC = AutocompleteFilterFactory("Entry Semester", "entry_semester")
FacultyGroupFAC = AutocompleteFilterFactory("Group", "staff_profile__user__groups")


class FacultyTeachingDepartmentFilterAC(ScopedAutocompleteFilter):
    """Autocomplete filter for departments taught by a faculty."""

    title = "Teaching Department"
    parameter_name = "section__curriculum_course__course__department"
    field_name = "department"
    lookup_map = (("section", "section__curriculum_course__course__department"),)
    target_model = Department
