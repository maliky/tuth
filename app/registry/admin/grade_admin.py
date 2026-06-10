"""Admin configuration for registry models."""

from typing import Optional, TypeAlias, cast

from django import forms
from django.contrib import admin
from django.db.models import Case, CharField, Count, F, QuerySet, Value, When
from django.db.models.functions import Cast, Concat
from django.urls import path, reverse
from django.utils.html import format_html
from django.contrib.admin.widgets import FilteredSelectMultiple
from import_export.admin import ImportExportModelAdmin

from app.people.models.student import Student
from app.registry.models.document import DocStatus, DocType

# from app.registry.admin.filters import GradeSecFlt
# from app.registry.admin.views import SectioGradeValueerAutocomplete
from app.registry.models.grade import Grade, GradeValue
from app.registry.admin.resources import GradeResource
from app.registry.admin.filters import GradeStdFlt
from app.registry.models.registration import Registration, RegistrationStatus
from app.registry.models.transcript import TranscriptRequest, TranscriptRequestStatus
from app.timetable.admin.filters import (
    SecBySemFlt,
    SemFltAC,
)
from app.timetable.admin.views import SecBySemAutocomplete
from app.timetable.models.semester import Semester
from app.timetable.models.section import Section
from simple_history.admin import SimpleHistoryAdmin
from guardian.admin import GuardedModelAdmin
from app.shared.admin.mixins import ScopedAutocompleteAdminMixin

SectionQueryT: TypeAlias = QuerySet[Section]
SemesterT: TypeAlias = Semester


@admin.register(GradeValue)
class GradeValueAdmin(SimpleHistoryAdmin, ImportExportModelAdmin, GuardedModelAdmin):
    """Admin interface for registry.models.GradeValues.

    Describe the different grades types
    """

    list_display = ("description", "number", "code")
    search_fields = ("code", "description")


@admin.register(Grade)
class GradeAdmin(
    ScopedAutocompleteAdminMixin,
    SimpleHistoryAdmin,
    ImportExportModelAdmin,
    GuardedModelAdmin,
):
    """Admin interface for :class:~app.registry.models.Grade.

    Shows student, section and grade fields in the list view with autocomplete
    lookups for student and section.
    """

    resource_class = GradeResource
    date_hierarchy = "graded_on"
    list_display = (
        "student",
        # "grade_code",
        "sec_short_code",
        "value__description",
        "section__semester",
        # "graded_on",
    )
    # list_filter = ['section__semester', GradeSecFlt]
    list_filter = [SemFltAC, SecBySemFlt, GradeStdFlt]
    autocomplete_fields = ("student", "section", "value")
    list_select_related = (
        "student__user",
        "section__semester",
        "section__curriculum_course__course",
        "value",
    )
    search_fields = (
        "student__student_id",
        "student__long_name",
        "student__user__first_name",
        "student__user__last_name",
        "student__user__username",
        "section__semester__academic_year__code",
        "section__semester__academic_year__long_name",
        "section__semester__number",
        "section__curriculum_course__course__short_code",
        "section__curriculum_course__course__code",
        "section__curriculum_course__course__department__code",
    )

    def get_urls(self):
        """Returns urls."""
        urls = super().get_urls()
        custom = [
            path(
                "section_by_semester_autocomplete/",
                self.admin_site.admin_view(
                    SecBySemAutocomplete.as_view(model_admin=self)
                ),
                name="section_by_semester_autocomplete",
            )
        ]
        return custom + urls

    def get_queryset(self, request):
        """Annotate a sortable section short code for changelist ordering."""
        qs = super().get_queryset(request)
        section_code = Case(
            When(
                section__curriculum_course__course__short_code__isnull=True,
                then=F("section__curriculum_course__course__code"),
            ),
            When(
                section__curriculum_course__course__short_code="",
                then=F("section__curriculum_course__course__code"),
            ),
            default=F("section__curriculum_course__course__short_code"),
            output_field=CharField(),
        )
        # Keep a DB-level key so sorting is alphabetical on section short code.
        return qs.annotate(
            section_sort_code=Concat(
                section_code,
                Value(":s"),
                Cast(F("section__number"), CharField()),
            )
        )

    @admin.display(description="Section", ordering="section_sort_code")
    def sec_short_code(self, obj):
        """Display the section short code and keep links in the FK field view."""
        section = cast(Section | None, getattr(obj, "section", None))
        if not section:
            return "-"
        return section.short_code

    @admin.display(description="Code")
    def grade_code(self, obj):
        """Display the letter grade in uppercase."""
        return (obj.value.code if obj.value else "").upper()

    def lookup_allowed(self, lookup, value):
        """Allow course filter used by course admin grade link."""
        if lookup == "section__curriculum_course__course__id__exact":
            return True
        return super().lookup_allowed(lookup, value)


__all__ = ["GradeAdmin", "GradeValueAdmin"]
