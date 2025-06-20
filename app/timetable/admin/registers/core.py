"""timetable.Core module."""

from django.contrib import admin
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin

from app.timetable.admin.inlines import SemesterInline
from app.timetable.admin.resources.core import SemesterResource
from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.semester import Semester


@admin.register(AcademicYear)
class AcademicYearAdmin(GuardedModelAdmin):
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
class SemesterAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    """Admin configuration for :class:~app.timetable.models.Semester.

    Provides import/export support and filters semesters by academic year.
    list_display shows the academic year, number and date range.
    """

    resource_class = SemesterResource
    list_display = ("academic_year", "number", "start_date", "end_date")
    list_filter = ("academic_year",)
    search_fields = ("academic_year__code", "academic_year__long_name")
