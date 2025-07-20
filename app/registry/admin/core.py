"""Admin configuration for registry models."""

from django.contrib import admin
from django.urls import path
from import_export.admin import ImportExportModelAdmin

from app.people.models.student import Student

# from app.registry.admin.filters import GradeSectionFilter
# from app.registry.admin.views import SectioGradeValueerAutocomplete
from app.registry.models.grade import Grade, GradeValue
from app.registry.models.registration import Registration
from app.timetable.admin.filters import (
    GradeSemesterFilterAc,
    SectionBySemesterFilter,
    SemesterFilter,
)
from app.timetable.admin.views import SectionBySemesterAutocomplete
from app.timetable.models.section import Section
from simple_history.admin import SimpleHistoryAdmin
from guardian.admin import GuardedModelAdmin

GradeValue


@admin.register(GradeValue)
class GradeValueAdmin(SimpleHistoryAdmin, ImportExportModelAdmin, GuardedModelAdmin):
    """Admin interface for registry.models.GradeValues.

    Describe the different grades types
    """

    list_display = ("number", "code", "description")
    search_fields = ("code", "description")


@admin.register(Grade)
class GradeAdmin(SimpleHistoryAdmin, ImportExportModelAdmin, GuardedModelAdmin):
    """Admin interface for :class:~app.registry.models.Grade.

    Shows student, section and grade fields in the list view with autocomplete
    lookups for student and section.
    """

    date_hiearchy = "grade_on"
    list_display = (
        "student",
        "value",
        "section",
        "section__semester",
        "graded_on",
    )
    # list_filter = ['section__semester', GradeSectionFilter]
    list_filter = [GradeSemesterFilterAc, SectionBySemesterFilter]
    search_fields = ("student__student_id", "section__semester")

    def get_urls(self):
        """Returns urls."""
        urls = super().get_urls()
        custom = [
            path(
                "section_by_semester_autocomplete/",
                self.admin_site.admin_view(
                    SectionBySemesterAutocomplete.as_view(model_admin=self)
                ),
                name="section_by_semester_autocomplete",
            )
        ]
        return custom + urls


@admin.register(Registration)
class RegistrationAdmin(SimpleHistoryAdmin, ImportExportModelAdmin, GuardedModelAdmin):
    """Allow students to register only for eligible sections."""

    list_display = ("student", "section", "status", "date_registered")
    autocomplete_fields = ("student", "section")
    search_fields = (
        "student__student_id",
        "section__program__course__code",
        "section__number",
    )
    list_filter = (SemesterFilter,)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Probably orverriding the default form for the model.

        List the program (course <-> curriculum) in which the student is enrolled.
        """
        if db_field.name == "section" and not request.user.is_superuser:
            try:
                student = request.user.student
            except Student.DoesNotExist:
                kwargs["queryset"] = Section.objects.none()
            else:
                kwargs["queryset"] = Section.objects.filter(
                    program__course__in=student.allowed_courses()
                )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
