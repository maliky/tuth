"""timetable.Core module."""

from django.contrib import admin
from django.db.models import Count
from django.urls import reverse
from django.utils.html import format_html
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin
from simple_history.admin import SimpleHistoryAdmin

from app.timetable.admin.inlines import SemesterInline
from app.timetable.admin.resources.core import SemesterResource
from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.semester import Semester
from app.timetable.models.term import Term


@admin.register(AcademicYear)
class AcademicYearAdmin(SimpleHistoryAdmin, GuardedModelAdmin):
    """Admin settings for :class:~app.timetable.models.AcademicYear.

    Displays academic year information and embeds semesters via
    SemesterInline. The listing is ordered by start date in descending
    order and grouped by the start date hierarchy.
    """

    list_display = ("long_name", "start_date", "end_date", "code")
    date_hierarchy = "start_date"
    inlines = [SemesterInline]
    ordering = ("-start_date",)


@admin.register(Semester)
class SemesterAdmin(SimpleHistoryAdmin, ImportExportModelAdmin, GuardedModelAdmin):
    """Admin configuration for :class:~app.timetable.models.Semester.

    Provides import/export support and filters semesters by academic year.
    list_display shows the academic year, number and date range.
    """

    resource_class = SemesterResource
    list_display = (
        "academic_year",
        "number",
        "start_date",
        "end_date",
        "section_count_link",
        "student_count_link",
    )
    list_filter = ("academic_year",)
    search_fields = ("academic_year__code", "academic_year__long_name")
    ordering = ("academic_year", "number")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            section_total=Count("section", distinct=True),
            student_total=Count("current_students", distinct=True),
        )

    @admin.display(description="Sections", ordering="section_total")
    def section_count_link(self, semester):
        count = getattr(semester, "section_total", None)
        if count is None:
            count = semester.sections.count()
        url = reverse("admin:timetable_section_changelist") + (
            f"?semester__id__exact={semester.id}"
        )
        return format_html('<a href="{}">{}</a>', url, count)

    @admin.display(description="Students", ordering="student_total")
    def student_count_link(self, semester):
        count = getattr(semester, "student_total", None)
        if count is None:
            count = semester.current_students.count()
        url = reverse("admin:people_student_changelist") + (
            f"?current_enrolled_semester__id__exact={semester.id}"
        )
        return format_html('<a href="{}">{}</a>', url, count)


@admin.register(Term)
class TermAdmin(SimpleHistoryAdmin, GuardedModelAdmin):
    """Admin configuration for :class:`~app.timetable.models.Term`.

    Mirrors :class:`SemesterAdmin` by listing each term's parent semester,
    number and date range. The ``number`` foreign key uses autocomplete to
    simplify selection.
    """

    list_display = ("semester", "number", "start_date", "end_date")
    list_filter = ("semester",)
    autocomplete_fields = ("semester",)
