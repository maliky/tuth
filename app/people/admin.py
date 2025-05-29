from django.contrib import admin

from .models import FacultyProfile, DonorProfile


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


@admin.register(DonorProfile)
class DonorProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "donor_id")
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "donor_id",
    )
    autocomplete_fields = ("user",)
