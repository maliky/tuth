from django.contrib import admin
from app.academics import Curriculum


class CurriculumFilter(admin.SimpleListFilter):
    title = "curriculum"
    parameter_name = "curriculum"

    def lookups(self, request, model_admin):
        return [(c.pk, c.title) for c in Curriculum.objects.all()]

    def queryset(self, request, qs):
        if self.value():
            return qs.filter(curriculum_id=self.value())

        return qs
