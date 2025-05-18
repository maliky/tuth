# app/admin/filters.py
from django.contrib import admin
from django.db.models import Q
from app.models import Curriculum


class CurriculumFilter(admin.SimpleListFilter):
    title = "curriculum"
    parameter_name = "curriculum"

    def lookups(self, request, model_admin):
        return [(c.pk, c.title) for c in Curriculum.objects.all()]

    def queryset(self, request, qs):
        if self.value():
            return qs.filter(
                Q(course__curriculan_id=self.value())
                | Q(prerequisite_course__curriculua_id=self.value())
            ).distinct()
        return qs
