"""timetable.Core module."""

from django import forms
from django.contrib import admin
from django.contrib import messages
from django.contrib.admin.helpers import ActionForm
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.urls import reverse
from django.utils.html import format_html
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin
from simple_history.admin import SimpleHistoryAdmin

from app.timetable.admin.filters import SemesterAcademicYearFilterAc
from app.timetable.admin.inlines import SemesterInline
from app.timetable.admin.core_resources import SemesterResource
from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.semester import Semester, SemesterStatus
from app.timetable.models.term import Term


class SemesterActionForm(ActionForm):
    """Action form used to select a status for bulk updates."""

    status = forms.ModelChoiceField(
        queryset=SemesterStatus.objects.all(), required=True, label="Status"
    )


@admin.register(AcademicYear)
class AcademicYearAdmin(SimpleHistoryAdmin, GuardedModelAdmin):
    """Admin settings for :class:~app.timetable.models.AcademicYear.

    Displays academic year information and embeds semesters via
    SemesterInline. The listing is ordered by start date in descending
    order and grouped by the start date hierarchy.
    """

    list_display = (
        "long_name",
        "start_date",
        "end_date",
        "code",
        "section_count_link",
        "student_count_link",
    )
    date_hierarchy = "start_date"
    inlines = [SemesterInline]
    ordering = ("-start_date",)

    def get_queryset(self, request):
        """Annotate section/student totals for academic year listings."""
        qs = super().get_queryset(request)
        return qs.annotate(
            section_total=Count("semester__section", distinct=True),
            student_total=Count(
                "semester__section__section_registrations__student", distinct=True
            ),
        )

    @admin.display(description="Sections", ordering="section_total")
    def section_count_link(self, academic_year):
        """Link to sections scoped to this academic year."""
        count = getattr(academic_year, "section_total", None)
        if count is None:
            count = (
                academic_year.semester_set.filter(section__isnull=False)
                .values_list("section__id", flat=True)
                .distinct()
                .count()
            )
        url = reverse("admin:timetable_section_changelist") + (
            f"?semester__academic_year__id__exact={academic_year.id}"
        )
        return format_html('<a href="{}">{}</a>', url, count)

    @admin.display(description="Students", ordering="student_total")
    def student_count_link(self, academic_year):
        """Link to registrations for the academic year."""
        count = getattr(academic_year, "student_total", None)
        if count is None:
            count = (
                academic_year.semester_set.filter(
                    section__section_registrations__student__isnull=False
                )
                .values_list("section__section_registrations__student_id", flat=True)
                .distinct()
                .count()
            )
        url = reverse("admin:registry_registration_changelist") + (
            f"?section__semester__academic_year__id__exact={academic_year.id}"
        )
        return format_html('<a href="{}">{}</a>', url, count)


@admin.register(Semester)
class SemesterAdmin(SimpleHistoryAdmin, ImportExportModelAdmin, GuardedModelAdmin):
    """Admin configuration for :class:~app.timetable.models.Semester.

    Provides import/export support and filters semesters by academic year.
    list_display shows the academic year, number and date range.
    """

    resource_class = SemesterResource
    action_form = SemesterActionForm
    actions = ("set_semester_status",)
    list_display = (
        "academic_year",
        "status",
        "number",
        "section_count_link",
        "student_count_link",
    )
    list_filter = (SemesterAcademicYearFilterAc,)
    list_editable = ("status",)
    # Search filter necessary here for termadmin search to complete
    search_fields = ("academic_year__code", "academic_year__long_name")
    ordering = ("academic_year", "number")

    @admin.action(description="Set status for selected semesters")
    def set_semester_status(self, request, queryset):
        """Bulk update semester status with registration-open validation."""
        status = request.POST.get("status")
        if not status:
            messages.error(request, "Select a status before running this action.")
            return
        status_obj = SemesterStatus.objects.filter(pk=status).first()
        if status_obj is None:
            messages.error(request, "Selected status was not found.")
            return
        # > uniqueness of opensemester is done at db level
        updated = 0
        for semester in queryset:
            semester.status = status_obj
            semester.save(update_fields=["status"])
            updated += 1
        messages.success(request, f"Updated {updated} semester(s).")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            section_total=Count("section", distinct=True),
            student_total=Count("section__section_registrations__student", distinct=True),
        )

    @admin.display(description="Sections", ordering="section_total")
    def section_count_link(self, semester):
        count = getattr(semester, "section_total", None)
        if count is None:
            count = semester.section_set.count()
        url = reverse("admin:timetable_section_changelist") + (
            f"?semester__id__exact={semester.id}"
        )
        return format_html('<a href="{}">{}</a>', url, count)

    @admin.display(description="Students", ordering="student_total")
    def student_count_link(self, semester):
        count = getattr(semester, "student_total", None)
        if count is None:
            count = (
                semester.section_set.filter(section_registrations__student__isnull=False)
                .values_list("section_registrations__student_id", flat=True)
                .distinct()
                .count()
            )
        url = reverse("admin:registry_registration_changelist") + (
            f"?section__semester__id__exact={semester.id}"
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
