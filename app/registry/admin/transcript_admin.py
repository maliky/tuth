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


@admin.register(TranscriptRequest)
class TranscriptRequestAdmin(
    ScopedAutocompleteAdminMixin, SimpleHistoryAdmin, GuardedModelAdmin
):
    """Allow students to request grade transcripts."""

    list_display = ("student", "status", "requested_at", "purpose")
    autocomplete_fields = ("student", "status")
    search_fields = (
        "student__student_id",
        "student__long_name",
        "student__user__first_name",
        "student__user__last_name",
        "status__code",
        "status__label",
    )
    # > See how I can make this a AC field and limit the number of semester to the used semesters
    list_filter = (SemFltAC,)


@admin.register(DocStatus, DocType, TranscriptRequestStatus)
class CurriStatusAdmin(admin.ModelAdmin):
    """Lookup admin for CurriStatus."""

    search_fields = ("code", "label")
    list_display = ("label",)


@admin.register(RegistrationStatus)
class RegioStatusAdmin(admin.ModelAdmin):
    """Registration status admin with registration totals."""

    list_display = ("label", "regio_count")

    def get_queryset(self, request):
        """Annotate registration totals for list display."""
        qs = super().get_queryset(request)
        return qs.annotate(registration_total=Count("registrations", distinct=True))

    @admin.display(description="Registrations", ordering="registration_total")
    def regio_count(self, obj):
        """Return the number of registrations using this status."""
        count = getattr(obj, "registration_total", None)
        if count is None:
            count = obj.registrations.count()
        url = reverse("admin:registry_registration_changelist") + (
            f"?status__id__exact={obj.pk}"
        )
        return format_html('<a href="{}">{}</a>', url, count)


__all__ = ["CurriStatusAdmin", "RegioStatusAdmin", "TranscriptRequestAdmin"]
