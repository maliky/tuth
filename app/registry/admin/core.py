"""Admin configuration for registry models."""

from django.contrib import admin
from django.urls import path, reverse
from import_export.admin import ImportExportModelAdmin

from app.people.models.student import Student
from app.registry.admin.filters import GradeSectionFilter

#from app.registry.admin.views import SectionBySemesterAutocomplete
from app.registry.models.class_roster import ClassRoster
from app.registry.models.grade import Grade, GradeType
from app.registry.models.registration import Registration
from app.shared.mixins import HistoricalAccessMixin
from app.timetable.admin.filters import (
    SectionBySemesterFilter,
    SemesterFilter,
    SemesterFilterAutocomplete,
)
from app.timetable.admin.views import SectionBySemesterAutocomplete
from app.timetable.models.section import Section


@admin.register(GradeType)
class GradeTypeAdmin(HistoricalAccessMixin, ImportExportModelAdmin, admin.ModelAdmin):
    """Admin interface for registry.models.GradeTypes.

    Describe the different grades types
    """

    list_display = ("number", "code", "description")
    search_fields = ("code", "description")


@admin.register(Grade)
class GradeAdmin(HistoricalAccessMixin, ImportExportModelAdmin, admin.ModelAdmin):
    """Admin interface for :class:~app.registry.models.Grade.

    Shows student, section and grade fields in the list view with autocomplete
    lookups for student and section.
    """

    list_display = (
        "student",
        "grade",
        "section",
        "section__semester",
        "graded_on",
    )
    # list_filter = ['section__semester', GradeSectionFilter]
    list_filter = [SemesterFilterAutocomplete, SectionBySemesterFilter]
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


@admin.register(ClassRoster)
class ClassRosterAdmin(ImportExportModelAdmin, HistoricalAccessMixin, admin.ModelAdmin):
    """Admin interface for :class:~app.registry.models.ClassRoster.

    Displays the section and counts enrolled students via student_count.
    The section foreign key is autocompleted for convenience.
    """

    list_display = ("section", "student_count", "last_updated")
    list_filter = (SemesterFilter,)
    search_fields = (
        "section__course__code",
        "section__number",
        "section__semester__code",
    )
    autocomplete_fields = ("section",)

    @admin.display(description="Students")
    def student_count(self, obj: ClassRoster) -> int:
        """Return number of students enrolled in this roster."""
        return obj.students.count()


@admin.register(Registration)
class RegistrationAdmin(ImportExportModelAdmin, HistoricalAccessMixin, admin.ModelAdmin):
    """Allow students to register only for eligible sections."""

    list_display = ("student", "section", "status", "date_registered")
    autocomplete_fields = ("student", "section")
    search_fields = (
        "student__student_id",
        "section__program__course__code",
        "section__number",
    )
    list_filter = (SemesterFilter,)

    def get_queryset(self, request):
        """Override the Set of object returned for tis page.

        Limit the registration to those of the student consulting the page.
        """
        qs = super().get_queryset(request)
        if request.user.is_superuser or self.has_historical_access(request.user):
            return self.get_historical_queryset(request)
        try:
            student = request.user.student
        except Student.DoesNotExist:
            return qs.none()
        qs = qs.filter(student=student)
        return self.filter_current_semester(qs)

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
