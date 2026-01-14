"""Filters for the registry models in Admin."""

from admin_searchable_dropdown.filters import AutocompleteFilter


class GradeSectionFilter(AutocompleteFilter):
    title = "Sections"
    field_name = "section"


class GradeStudentFilter(AutocompleteFilter):
    """Autocomplete student filter for grade listings."""

    title = "Student"
    field_name = "student"
