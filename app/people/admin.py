from django.contrib import admin

from .models import FacultyProfile


@admin.register(FacultyProfile)
class InstructorProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "department", "college", "position")
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "department",
    )
    autocomplete_fields = ("user", "college", "courses")
