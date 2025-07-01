"""Admin configuration for registry models."""

from app.people.models.student import Student
from app.registry.models.registration import Registration
from app.timetable.models.section import Section
from django.contrib import admin

from app.shared.mixins import HistoricalAccessMixin

from app.registry.models.class_roster import ClassRoster
from app.registry.models.grade import Grade


@admin.register(Grade)
class GradeAdmin(HistoricalAccessMixin, admin.ModelAdmin):
    """Admin interface for :class:~app.registry.models.Grade.

    Shows student, section and grade fields in the list view with autocomplete
    lookups for student and section.
    """

    list_display = (
        "student",
        "section",
        "letter_grade",
        "numeric_grade",
        "graded_on",
    )
    search_fields = (
        "student__student_id",
        "student__user__username",
        "student__user__first_name",
        "student__user__last_name",
        "section__course__code",
        "section__number",
    )
    autocomplete_fields = ("student", "section")


@admin.register(ClassRoster)
class ClassRosterAdmin(admin.ModelAdmin):
    """Admin interface for :class:~app.registry.models.ClassRoster.

    Displays the section and counts enrolled students via student_count.
    The section foreign key is autocompleted for convenience.
    """

    list_display = ("section", "student_count", "last_updated")
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
class RegistrationAdmin(HistoricalAccessMixin, admin.ModelAdmin):
    """Allow students to register only for eligible sections."""

    list_display = ("student", "section", "status", "date_registered")
    autocomplete_fields = ("student", "section")
    search_fields = (
        "student__student_id",
        "section__program__course__code",
        "section__number",
    )

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
