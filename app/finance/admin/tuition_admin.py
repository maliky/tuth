"""Admin for career-aware tuition policy."""

from __future__ import annotations

from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from app.finance.models.tuition import TuitionRate


@admin.register(TuitionRate)
class TuitionRateAdmin(SimpleHistoryAdmin):
    """Manage tuition rates by semester and academic career."""

    list_display = (
        "semester",
        "academic_career",
        "currency",
        "tuition_per_credit",
        "foreigner_tuition_per_credit",
        "source",
    )
    list_filter = ("academic_career", "currency", "semester")
    autocomplete_fields = ("semester",)
    search_fields = (
        "semester__academic_year__code",
        "academic_career",
        "source",
    )
