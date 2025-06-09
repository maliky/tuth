"""timetable.Core module."""

from django.contrib import admin
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin

from app.timetable.admin.inlines import SemesterInline
from app.timetable.admin.resources.core import SemesterResource
from app.timetable.models import AcademicYear, Semester


@admin.register(AcademicYear)
class AcademicYearAdmin(GuardedModelAdmin):
    """Admin settings for :class:`~app.timetable.models.AcademicYear`."""

    list_display = ("long_name", "start_date", "code")
    date_hierarchy = "start_date"
    inlines = [SemesterInline]
    ordering = ("-start_date",)
    search_fields = ("code",)


@admin.register(Semester)
class SemesterAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    """Admin configuration for :class:`~app.timetable.models.Semester`."""

    resource_class = SemesterResource
    list_filter = ("academic_year",)
    search_fields = ("academic_year__code", "academic_year__long_name")
