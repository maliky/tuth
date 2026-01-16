"""app.timetable.admin.section_registers module."""

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from app.academics.admin.filters import CurriculumFilterAC
from app.people.models.faculty import Faculty
from app.people.models.student import Student
from app.registry.admin.inlines import GradeInline
from app.shared.admin.core import get_current_semester
from app.shared.admin.filters import BaseCollegeFilter
from app.shared.admin.mixins import CollegeRestrictedAdmin
from app.timetable.admin.filters import SectionFacultyFilterAc, SemesterFilterAC
from app.timetable.admin.inlines import SecSessionInline
from app.timetable.admin.section_resources import SectionResource
from app.timetable.models.section import Section


@admin.register(Section)
class SectionAdmin(CollegeRestrictedAdmin):
    """Admin interface for Section.

    list_display includes semester, course and faculty information while
    inlines manage sessions and grade.
    Filtering by curriculum is available through list_filter.
    """

    resource_class = SectionResource
    college_field = "curriculum_course__curriculum__college"
    list_display = (
        "curriculum_course",
        "number",
        "semester",
        "faculty_link",
        "available_seats",
        "space_codes",
        "session_count",
        "credit_hours",
        "curriculum_display",
    )
    # need to be a field of the section
    # list_editable = ("curriculum_course__curriculum",)
    inlines = [SecSessionInline, GradeInline]
    # Added curriculum filtering per section list requirements.
    list_filter = [
        SectionFacultyFilterAc,
        CurriculumFilterAC,
        SemesterFilterAC,
    ]
    autocomplete_fields = (
        "semester",
        "faculty",
    )

    # Join related tables to reduce queries when pulling sections.
    list_select_related = (
        "curriculum_course",
        "curriculum_course__curriculum",
        "semester",
        "faculty",
    )

    search_fields = (
        "^curriculum_course__course__short_code",
    )  # fast starts-with on indexed code

    def get_queryset(self, request):
        """Prefetch sessions and limit sections to the current faculty."""
        qs = super().get_queryset(request).prefetch_related("sessions__room")
        if request.user.is_superuser:
            return qs
        try:
            faculty = request.user.staff.faculty
        except (AttributeError, Faculty.DoesNotExist):
            return qs.none()
        return qs.filter(faculty=faculty)

    def get_search_results(self, request, queryset, search_term):
        """Filter section autocomplete results by selected student when provided."""
        qs, use_distinct = super().get_search_results(request, queryset, search_term)
        student_id = request.GET.get("student")
        is_registration_lookup = (
            request.GET.get("app_label") == "registry"
            and request.GET.get("model_name") == "registration"
            and request.GET.get("field_name") == "section"
        )
        if is_registration_lookup:
            current_semester = get_current_semester()
            if not current_semester or not current_semester.is_registration_open():
                return qs.none(), use_distinct
            qs = qs.filter(semester=current_semester)
            if not student_id:
                return qs.none(), use_distinct
        if not student_id:
            return qs, use_distinct
        try:
            student_pk = int(student_id)
        except (TypeError, ValueError):
            return qs, use_distinct
        student = Student.objects.filter(pk=student_pk).first()
        if not student:
            return qs.none(), use_distinct
        qs = qs.filter(curriculum_course__course__in=student.allowed_courses())
        return qs, use_distinct

    def lookup_allowed(self, lookup, value, request=None):
        """Allow scoped academic year/college links from related admins."""
        if lookup in {
            "semester__academic_year",
            "semester__academic_year__id__exact",
            "curriculum_course__curriculum__college__id__exact",
        }:
            return True
        return super().lookup_allowed(lookup, value, request)

    @admin.display(description="SecSessions")
    def all_sessions(self, obj: Section) -> str:
        """Return a human-readable summary of this Section’s sessions.

        For example: “Mon 09:00–10:00 (Rm 101); Wed 09:00–10:00 (Rm 101)”
        """
        slots = []
        for sess in obj.sessions.all():
            slots.append(f"{sess.schedule} ({sess.room})")

        return "; ".join(slots) or "--"

    @admin.display(description="# SecSessions")
    def session_count(self, obj: Section) -> int:
        """Return the number of sessions attached to this section."""
        return obj.sessions.count()

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
