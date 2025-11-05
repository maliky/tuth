"""Filters module."""

from admin_searchable_dropdown.filters import (
    AutocompleteFilter,
    AutocompleteFilterFactory,
)
# https://pypi.org/project/django-admin-list-filters/
from django_admin_filters import MultiChoice  
from django.contrib import admin
from django.db.models import Count
from django.urls import reverse


# class CollegeChoicesFilter(MultiChoice):
#     FILTER_LABEL = "College"
#     BUTTON_LABEL = "Filter"
    
CurriculumCourseFilterAc = AutocompleteFilterFactory(
    "Curriculum",  # title
    "curriculum_course__curriculum",  # look-up path ( → cuccirulm )
    # use_pk_exact=False
)

ProgramFilterAc = AutocompleteFilterFactory(
    "Curriculum",  # title
    "in_curriculum_courses__curriculum",  # look-up path ( → cuccirulm )
    # use_pk_exact=False
)

DepartmentFilterAc = AutocompleteFilterFactory(
    "Department",  # title
    "course__department",
)
CurriculumFilterAc = AutocompleteFilterFactory(
    "Curriculum",  # title
    "curriculum",
)


class CurriculumBySemesterFilterAc(AutocompleteFilter):
    """Returns the curriculum having section for a specific semester."""

    title = "Curriculum"
    field_name = "curriculum_course__curriculum"

    def get_autocomplete_url(self, request, model_admin):
        """Get the urls registered in SectionAdmin.get_urls."""
        base = reverse("admin:curriculum_by_semester_ac")
        # semester_id = request.GET.get("semester")
        return base


class CurriculumFilter(admin.SimpleListFilter):
    title = "curriculum"
    parameter_name = "curriculum"

    def lookups(self, request, model_admin):
        """Update the filter so only curricula of the already selected college show."""
        qs = model_admin.get_queryset(request)
        college_id = request.GET.get("college__id__exact")

        if college_id:
            qs = qs.filter(college_id=college_id)
        curricula = (
            qs.values("curriculum", "curriculum__short_name")
            .annotate(count=Count("pk"))
            .filter(curriculum__isnull=False, count__gt=0)
            .order_by("curriculum__short_name")
        )

        return [(c["curriculum"], c["curriculum__short_name"]) for c in curricula]

    def queryset(self, request, qs):
        """Overide the queryset returning a curriculum."""
        if self.value():
            return qs.filter(curriculum_id=self.value())

        return qs
