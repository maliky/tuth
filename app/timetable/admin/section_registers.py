"""app.timetable.admin.section_registers module."""

from django.contrib import admin
from django.db.models import F, Value
from django.db.models.functions import Coalesce, Concat
from django.http import HttpRequest
from django.urls import reverse
from django.utils.html import format_html

from app.academics.admin.filters import CurriFltAC
from app.academics.models.curriculum_course import CurriCourse
from app.people.models.faculty import Faculty
from app.people.models.student import Student
from app.registry.admin.inlines import GradeIL
from app.shared.admin.mixins import CollegeRestrictedAdmin, ProtectedDeleteAdminMixin
from app.timetable.admin.filters import (
    CollegeFltAC,
    SectionFacultyFltAc,
    SemesterFltAC,
)
from app.timetable.admin.inlines import SecSessionIL
from app.timetable.admin.section_resources import SectionResource
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester


def _is_registration_lookup(request: HttpRequest) -> bool:
    """Return True when the request targets registration section autocomplete."""
    return (
        request.GET.get("app_label") == "registry"
        and request.GET.get("model_name") == "registration"
        and request.GET.get("field_name") == "section"
    )


@admin.register(Section)
class SectionAdmin(ProtectedDeleteAdminMixin, CollegeRestrictedAdmin):
    """Admin interface for Section.

    list_display includes semester, course and faculty information while
    inlines manage sessions and grade.
    Flting by curriculum is available through list_filter.
    """

    resource_class = SectionResource
    college_field = "curriculum_course__curriculum__college"
    list_display = (
        "curriculum_course_display",
        "session_count",
        "faculty_link",
        "space_codes",
        "available_seats",
        "credit_hours",
        # "curriculum_display",
        "semester",
    )
    # need to be a field of the section
    # list_editable = ("curriculum_course__curriculum",)
    inlines = [SecSessionIL, GradeIL]
    # Added curriculum filtering per section list requirements.
    list_filter = [
        CollegeFltAC,
        SectionFacultyFltAc,
        CurriFltAC,
        SemesterFltAC,
    ]
    autocomplete_fields = ("semester", "faculty")

    # Join related tables to reduce queries when pulling sections.
    list_select_related = (
        "curriculum_course",
        "curriculum_course__course",
        "curriculum_course__curriculum",
        "curriculum_course__curriculum__college",
        "semester",
        "faculty",
    )
    # fast starts-with on indexed code
    search_fields = ("^curriculum_course__course__short_code",)

    def get_queryset(self, request):
        """Prefetch sessions and limit sections to the current faculty."""
        qs = (
            super()
            .get_queryset(request)
            .prefetch_related("sessions__room")
            .annotate(
                curriculum_course_str=Concat(
                    Coalesce(
                        F("curriculum_course__course__short_code"),
                        F("curriculum_course__course__code"),
                    ),
                    Value(" :: "),
                    F("curriculum_course__curriculum__college__code"),
                    Value("_"),
                    F("curriculum_course__curriculum__short_name"),
                )
            )
        )
        if _is_registration_lookup(request):
            # Scope registration lookups to the semester open for registration.
            open_semester, error_message = Semester.registration_open_semester()
            if error_message:
                # > need to do something with the error message
                return qs.none()

            return qs.filter(semester=open_semester)
        # > or registrar roles...?
        if request.user.is_superuser:
            return qs
        try:
            faculty = request.user.staff.faculty
        except (AttributeError, Faculty.DoesNotExist):
            return qs.none()
        return qs.filter(faculty=faculty)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Sort curriculum course choices alphabetically by display components."""
        if db_field.name == "curriculum_course":
            kwargs["queryset"] = CurriCourse.objects.select_related(
                "course",
                "curriculum__college",
            ).order_by(
                "course__short_code",
                "course__code",
                "curriculum__college__code",
                "curriculum__short_name",
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_protected_delete_single_message(
        self, request: HttpRequest, obj, protected_count: int
    ) -> str:
        """Return section-specific message for protected single deletes."""
        return (
            "Cannot delete section because grades depend on it "
            f"({protected_count} protected record(s)). Reassign grades first."
        )

    def get_protected_delete_bulk_message(
        self, request: HttpRequest, protected_count: int
    ) -> str:
        """Return section-specific message for protected bulk deletes."""
        return (
            "Bulk delete stopped: some sections have grades attached "
            f"({protected_count} protected record(s)). Reassign grades first."
        )

    def get_search_results(self, request, queryset, search_term):
        """Filter section autocomplete results by selected student when provided."""
        qs, use_distinct = super().get_search_results(request, queryset, search_term)
        # student_id = request.GET.get("student")
        # if not student_id:
        #     if _is_registration_lookup(request):
        #         return qs.none(), use_distinct
        #     return qs, use_distinct

        # try:
        #     student_pk = int(student_id)
        # except (TypeError, ValueError):
        #     return qs, use_distinct

        # student = Student.objects.filter(pk=student_pk).first()
        # if not student:
        #     return qs.none(), use_distinct

        # qs = qs.filter(curriculum_course__course__in=student.allowed_courses())
        return qs, use_distinct

    def lookup_allowed(self, lookup, value, request=None):
        """Allow scoped academic year/college links from related admins."""
        if lookup in {
            "semester__academic_year",
            "semester__academic_year__id__exact",
            "curriculum_course__curriculum__college",
            "curriculum_course__curriculum__college__id__exact",
        }:
            return True
        return super().lookup_allowed(lookup, value, request)

    @admin.display(description="# Sessions")
    def session_count(self, obj: Section) -> str:
        """Return the section number and session count label."""
        return f"{obj.number}/{obj.sessions.count()}"

    @admin.display(description="Curriculum Course", ordering="curriculum_course_str")
    def curriculum_course_display(self, obj: Section) -> str:
        """Return the curriculum course label."""
        return str(obj.curriculum_course)

    @admin.display(description="Credits")
    def credit_hours(self, obj: Section) -> int:
        """Return credit hours for this section's curriculum_course."""
        return obj.curriculum_course.credit_hours_id or 3

    @admin.display(description="Curriculum", ordering="curriculum_course__curriculum")
    def curriculum_display(self, obj: Section) -> str:
        """Return the curriculum name for the section listing."""
        return str(obj.curriculum_course.curriculum)

    @admin.display(description="Faculty", ordering="faculty")
    def faculty_link(self, obj: Section) -> str:
        """Link faculty names to their admin profile."""
        faculty = obj.faculty
        if not faculty:
            return "-"
        url = reverse("admin:people_faculty_change", args=[faculty.pk])
        return format_html('<a href="{}">{}</a>', url, faculty)
