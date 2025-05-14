# app/admin.py
from django.contrib import admin
from guardian.admin import GuardedModelAdmin  # object-level perms
from import_export import resources
from import_export.admin import ImportExportModelAdmin

from app.models import (
    AcademicYear,
    College,
    Course,
    Curriculum,
    Room,
    Section,
    Term,
    Prerequisite,
)

# ────────────────────────────────────────────────────────────
#  Import-export “resource” helpers (optional)
# ────────────────────────────────────────────────────────────


class CurriculumResource(resources.ModelResource):
    class Meta:
        model = Curriculum
        fields = (
            "id",
            "title",
            "level",
            "academic_year",
            "college__code",
            "is_active",
        )
        export_order = fields


class CourseResource(resources.ModelResource):
    class Meta:
        model = Course
        exclude = ("description",)  # example: omit long text


# ────────────────────────────────────────────────────────────
#  Inline helpers
# ────────────────────────────────────────────────────────────


class TermInline(admin.TabularInline):
    """Edit the three terms directly on the Academic-year screen."""

    model = Term
    extra = 0
    max_num = 3
    fields = ("number", "start_date", "end_date")
    ordering = ("number",)


class SectionInline(admin.TabularInline):
    """Quickly add sections from the *Course* screen."""

    model = Section
    extra = 0
    fields = ("number", "term", "instructor", "room", "max_seats")
    ordering = ("term__academic_year__starting_date", "term__number", "number")


# ────────────────────────────────────────────────────────────
#  Admin classes
# ────────────────────────────────────────────────────────────


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("name", "building", "standard_capacity", "exam_capacity")
    search_fields = ("name", "building__short_name", "building__full_name")


@admin.register(AcademicYear)
class AcademicYearAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    """
    Academic-year with its Terms inline.
    """

    list_display = ("long_name", "starting_date", "short_name")
    date_hierarchy = "starting_date"
    inlines = [TermInline]
    ordering = ("-starting_date",)
    search_fields = ("long_name", "short_name")


@admin.register(Term)
class TermAdmin(GuardedModelAdmin):
    list_display = ("__str__", "academic_year", "number", "start_date", "end_date")
    list_filter = ("academic_year", "number")
    search_fields = ("academic_year__long_name",)
    ordering = ("-academic_year__starting_date", "number")
    autocomplete_fields = ("academic_year",)


@admin.register(College)
class CollegeAdmin(admin.ModelAdmin):
    list_display = ("code", "fullname", "current_dean")
    search_fields = ("code", "fullname")


@admin.register(Curriculum)
class CurriculumAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    """
    GuardedModelAdmin respects django-guardian object permissions.
    """

    resource_class = CurriculumResource
    list_display = ("title", "level", "academic_year", "college", "is_active")
    list_filter = ("college", "level", "academic_year", "is_active")
    search_fields = ("title",)
    autocomplete_fields = ("college", "academic_year")
    ordering = ("-academic_year__starting_date", "title")


@admin.register(Section)
class SectionAdmin(GuardedModelAdmin):
    """
    Stand-alone edit for sections (useful for bulk changes).
    """

    list_display = (
        "long_code",
        "course",
        "term",
        "instructor",
        "room",
        "max_seats",
    )
    list_filter = ("term__academic_year", "term__number", "course__curriculum__college")
    autocomplete_fields = ("course", "term", "instructor", "room")
    search_fields = (
        "course__code",
        "course__title",
        "instructor__username",
        "room__name",
    )
    ordering = (
        "-term__academic_year__starting_date",
        "term__number",
        "course__code",
        "number",
    )


class PrerequisiteInline(admin.TabularInline):
    """
    Two inlines give a full 360° view:

    • `source`   – courses for which THIS course is the prerequisite
    • `target`   – prerequisites that THIS course requires
    """

    model = Prerequisite  # the through model
    fk_name = "course"
    verbose_name_plural = "Is prerequisite for"
    extra = 0
    autocomplete_fields = ("prerequisite_course",)  


from django.contrib import admin
from app.models.academics import Prerequisite


class RequiresInline(admin.TabularInline):
    """
    Prerequisites that *this* course **needs**.

    Example:  “CS201 requires → [CS101]”
    Stored row: course = CS201 , prerequisite_course = CS101
    """
    model = Prerequisite          #
    fk_name = "course"            # this course is the dependent one
    verbose_name = "required prerequisite"
    verbose_name_plural = "Prerequisites this course needs"
    extra = 0
    autocomplete_fields = ("prerequisite_course",)


class RequiredByInline(admin.TabularInline):
    """
    Courses that **depend** on *this* course.

    Example:  “[CS201] requires CS101”  → viewed on the CS101 page
    Stored row: course = CS201 , prerequisite_course = CS101
    """
    model = Prerequisite
    fk_name = "prerequisite_course"      # this course is the prerequisite
    verbose_name = "dependent course"
    verbose_name_plural = "Courses that require this course"
    extra = 0
    autocomplete_fields = ("course",)
