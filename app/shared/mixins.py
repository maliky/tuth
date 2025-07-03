"""Shared mixins for admin and views."""

from __future__ import annotations

from typing import Iterable

from django.http import HttpRequest

from app.people.models.role_assignment import RoleAssignment
from app.timetable.models.semester import Semester


class HistoricalAccessMixin:
    """Allow privileged roles to bypass current semester filtering."""

    historical_roles: Iterable[str] = {
        "registrar",
        "financial_officer",
        "enrollment_officer",
    }

    def has_historical_access(self, user) -> bool:
        """Return True if user has a role with historical privileges."""

        return RoleAssignment.objects.filter(
            user=user, role__in=self.historical_roles
        ).exists()

    def current_semester(self) -> Semester | None:
        """Return the most recent semester or None if none exist."""

        return Semester.objects.order_by("-start_date").first()

    def filter_current_semester(self, qs):
        """Limit queryset to the latest semester if possible."""

        sem = self.current_semester()
        if sem is None:
            return qs
        model = qs.model._meta.model_name
        if model == "grade":
            return qs.filter(section__semester=sem)
        if model == "registration":
            return qs.filter(section__semester=sem)
        if model == "financialrecord":
            return qs.filter(student__current_enroled_semester=sem)
        if model == "paymenthistory":
            return qs.filter(financial_record__student__current_enroled_semester=sem)
        if hasattr(qs.model, "semester_id"):
            return qs.filter(semester=sem)
        return qs

    # ─── Overridable helpers ────────────────────────────────────────────────
    def get_historical_queryset(self, request: HttpRequest):
        """Return queryset ignoring semester limitations."""

        return super().get_queryset(request)  # type: ignore[misc]

    # ─── Django admin hook ──────────────────────────────────────────────────
    def get_queryset(self, request: HttpRequest):  # type: ignore[override]
        """Filter by semester unless user has historical access."""

        qs = super().get_queryset(request)  # type: ignore[misc]
        if request.user.is_superuser or self.has_historical_access(request.user):
            return self.get_historical_queryset(request)
        return self.filter_current_semester(qs)
