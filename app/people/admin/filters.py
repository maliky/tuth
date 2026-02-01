"""Admin list filters for people app."""

from admin_searchable_dropdown.filters import AutocompleteFilterFactory

from app.academics.models.curriculum_course import CurriculumCourse
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


class StudentCurriculumCourseFilterAC(ScopedAutocompleteFilter):
    """Autocomplete filter for students by registered curriculum course."""

    title = "Curriculum course"
    parameter_name = "student_registrations__section__curriculum_course"
    field_name = "curriculum_course"
    lookup_map = (
        ("student_registrations", "student_registrations__section__curriculum_course"),
    )
    target_model = CurriculumCourse
