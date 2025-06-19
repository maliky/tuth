"""Filters module."""

from django.contrib import admin
from django.db.models import Count


class CurriculumFilter(admin.SimpleListFilter):
    title = "curriculum"
    parameter_name = "curriculum"

    def lookups(self, request, model_admin):
        """Update the filter so only curricula of the already selecte college show."""
        qs = model_admin.get_queryset(request)
        college_id = request.GET.get("college__id__exact")

        if college_id:
            qs = qs.filter(college_id=college_id)
        curricula = (
            qs.values("curriculum", "curriculum__short_name")
            .annotate(count=Count("pk"))
            .filter(curriculum__isnull=False, count__gt=0)
            .order_by("curriculum__short_name")
        )

        return [(c["curriculum"], c["curriculum__short_name"]) for c in curricula]

    def queryset(self, request, qs):
        """Overide the queryset returning a curriculum."""
        if self.value():
            return qs.filter(curriculum_id=self.value())

        return qs
