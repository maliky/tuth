"""Admin configuration for registry models."""

from django.contrib import admin

from app.registry.models import ClassRoster, Grade


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    """Admin interface for :class:`~app.registry.models.Grade`."""

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
    """Admin interface for :class:`~app.registry.models.ClassRoster`."""

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
