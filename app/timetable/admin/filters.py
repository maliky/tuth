"""Filters for the registry models in Admin."""

from urllib.parse import urlencode

from admin_searchable_dropdown.filters import (
    AutocompleteFilter,
    AutocompleteFilterFactory,
    _get_rel_model,
)
from django.contrib import admin
from django.urls import reverse

from app.people.models.faculty import Faculty
from app.shared.admin.filters import (
    BaseCollegeFilter,
    ScopedAutocompleteFilter,
    _get_lookup_path,
    _related_qs_for_lookup,
)
from app.timetable.models import Semester

SEMESTER_FIELD_LOOKPS = (
    ("semester", "semester"),
    ("section", "section__semester"),
    ("curriculum_course", "curriculum_course__sections__semester"),
    ("payment", "payment_student__last_enrolled_semester"),
    ("student", "student__last_enrolled_semester"),
)

SemesterAcademicYearFilterAc = AutocompleteFilterFactory(
    "Academic year",
    "academic_year",
    use_pk_exact=False,  # > what advantages is there to use_pk_exact ?
)


class SectionCollegeFilter(BaseCollegeFilter):
    field_path = "curriculum_course__curriculum__college"
    parameter_name = "curriculum_course__curriculum__college__id__exact"


SectionFacultyFilterAc = AutocompleteFilterFactory("Faculty", "faculty")


class SecSessionFacultyFilterAc(ScopedAutocompleteFilter):
    """Autocomplete filter for session sections by faculty."""

    title = "Faculty"
    parameter_name = "section__faculty"
    field_name = "faculty"
    lookup_map = (("section", "section__faculty"),)
    target_model = Faculty


class SectionBySemesterFilter(AutocompleteFilter):
    """Dropdow for Section dependings on Semester filter."""

    title = "Section"
    field_name = "section"

    def get_autocomplete_url(self, request, model_admin):
        """Get the url registered in GradeAdmin.get_urls."""
        base = reverse("admin:section_by_semester_autocomplete")
        semester_id = request.GET.get("section__semester")
        return (
            f"{base}?{urlencode({'section__semester': semester_id})}"
            if semester_id
            else base
        )


class SemesterFilterAC(ScopedAutocompleteFilter):
    """Autocomplete filter constrained to semesters present in the queryset."""

    title = "Semester"
    is_placeholder_title = True
    parameter_name = "semester"
    field_name = "semester"
    lookup_map = SEMESTER_FIELD_LOOKPS
    target_model = Semester
