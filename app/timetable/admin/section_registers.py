"""app.timetable.admin.section_registers module."""

import re
from typing import cast

from django.contrib import admin
from django.contrib.auth.models import User
from django.db.models import F, Q, Value
from django.db.models.functions import Coalesce, Concat
from django.http import HttpRequest
from django.urls import reverse
from django.utils.html import format_html

from app.academics.admin.filters import CurriFltAC
from app.academics.models.curriculum_course import CurriCrs
from app.people.models.faculty import Faculty
from app.people.models.student import Student
from app.registry.admin.inlines import GradeIL
from app.shared.admin.mixins import (
    CollegeRestrictedAdmin,
    CollegeRestrictedQueryMixin,
    ProtectedDeleteAdminMixin,
)
from app.shared.auth.perms import UserRole
from app.timetable.admin.filters import (
    CollegeFltAC,
    SectionFacultyFltAc,
    SemFltAC,
)
from app.timetable.admin.inlines import SecSessionIL
from app.timetable.admin.section_resources import SecResource
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester

REGISTRAR_SECTION_ROLE_LABELS = frozenset(
    {
        UserRole.REGISTRAR.value.label,
        UserRole.REGISTRAR_OFFICER.value.label,
    }
)
VPAA_SECTION_ROLE_LABELS = frozenset(
    {
        "VPAA",
        UserRole.VPAA.value.label,
    }
)
COLLEGE_SECTION_ROLE_LABELS = frozenset(
    {
        UserRole.DEAN.value.label,
    }
)
SECTION_CODE_RE = re.compile(
    r"^(?P<course>[a-z]+\d+[a-z]?)(?:\s*(?:s|sec|section)?\s*(?P<number>\d+))?$",
    re.IGNORECASE,
)


def _is_regio_lookup(request: HttpRequest) -> bool:
    """Return True when the request targets registration section autocomplete."""
    return (
        request.GET.get("app_label") == "registry"
        and request.GET.get("model_name") == "registration"
        and request.GET.get("field_name") == "section"
    )


def _can_view_all_sections(request: HttpRequest) -> bool:
    """Return whether the user may bypass faculty-only section scoping."""
    user = cast(User, request.user)
    return (
        user.has_perm("timetable.view_section")
        and user.groups.filter(
            name__in=REGISTRAR_SECTION_ROLE_LABELS | VPAA_SECTION_ROLE_LABELS
        ).exists()
    )


def _can_view_college_sections(request: HttpRequest) -> bool:
    """Return whether the user may view college-scoped sections."""
    user = cast(User, request.user)
    return (
        user.has_perm("timetable.view_section")
        and user.groups.filter(name__in=COLLEGE_SECTION_ROLE_LABELS).exists()
    )


def _section_code_query(search_term: str) -> Q:
    """Return a section-code query for inputs like ENVS208:s1 or ENVS208 1."""
    normalized = re.sub(r"[:_-]+", " ", search_term.strip())
    normalized = re.sub(r"\s+", " ", normalized)
    match = SECTION_CODE_RE.match(normalized)
    if not match:
        return Q()
    course_code = match.group("course")
    query = Q(curriculum_course__course__short_code__iexact=course_code) | Q(
        curriculum_course__course__code__iexact=course_code
    )
    section_number = match.group("number")
    if section_number:
        query &= Q(number=int(section_number))
    return query


@admin.register(Section)
class SecAdmin(ProtectedDeleteAdminMixin, CollegeRestrictedAdmin):
    """Admin interface for Section.

    list_display includes semester, course and faculty information while
    inlines manage sessions and grade.
    Flting by curriculum is available through list_filter.
    """

    resource_class = SecResource
    college_field = "curriculum_course__curriculum__college"
    list_display = (
        "curri_crs_display",
        "session_count",
        "faculty_link",
        "space_codes",
        "available_seats",
        "credit_hours",
        # "curri_display",
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
        SemFltAC,
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
    search_fields = (
        "^curriculum_course__course__short_code",
        "curriculum_course__course__code",
        "curriculum_course__course__title",
        "curriculum_course__course__department__code",
    )

    def _get_dft_sem(self, request: HttpRequest) -> Semester | None:
        """Return the default semester used when creating sections."""
        # Prefer the semester open for registration when available.
        open_semester, _error_message = Semester.regio_open_sem()
        return open_semester or Semester.get_current_sem()

    def get_changeform_initial_data(
        self, request: HttpRequest
    ) -> dict[str, str | list[str]]:
        """Prefill semester on section add form with the best available default."""
        initial = super().get_changeform_initial_data(request)
        default_semester = self._get_dft_sem(request)
        if default_semester and "semester" not in initial:
            initial["semester"] = str(default_semester.pk)
        return initial

    def _section_queryset(self, request: HttpRequest, *, unrestricted: bool):
        """Return annotated sections, optionally bypassing college scoping."""
        base_qs = (
            super(CollegeRestrictedQueryMixin, self).get_queryset(request)
            if unrestricted
            else super().get_queryset(request)
        )
        return base_qs.prefetch_related("sessions__room").annotate(
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

    def get_queryset(self, request):
        """Prefetch sessions and limit sections to the current faculty."""
        can_view_all_sections = request.user.is_superuser or _can_view_all_sections(
            request
        )
        qs = self._section_queryset(request, unrestricted=can_view_all_sections)
        if _is_regio_lookup(request):
            # Scope registration lookups to the semester open for registration.
            open_semester, error_message = Semester.regio_open_sem()
            if error_message:
                # > need to do something with the error message
                return qs.none()

            return qs.filter(semester=open_semester)
        # Registrar roles intentionally bypass faculty/college scoping.
        if can_view_all_sections:
            return qs
        if _can_view_college_sections(request):
            if self.get_user_college(request) is None:
                return qs.none()
            return qs
        try:
            faculty = request.user.staff.faculty
        except (AttributeError, Faculty.DoesNotExist):
            return qs.none()
        return qs.filter(faculty=faculty)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Sort curriculum course choices alphabetically by display components."""
        if db_field.name == "curriculum_course":
            kwargs["queryset"] = CurriCrs.objects.select_related(
                "course",
                "curriculum__college",
            ).order_by(
                "course__short_code",
                "course__code",
                "curriculum__college__code",
                "curriculum__short_name",
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_protected_delete_single_msg(
        self, request: HttpRequest, obj, protected_count: int
    ) -> str:
        """Return section-specific message for protected single deletes."""
        return (
            "Cannot delete section because grades depend on it "
            f"({protected_count} protected record(s)). Reassign grades first."
        )

    def get_protected_delete_bulk_msg(
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
        section_query = _section_code_query(search_term)
        if section_query:
            qs = qs | queryset.filter(section_query)
            use_distinct = True
        # student_id = request.GET.get("student")
        # if not student_id:
        #     if _is_regio_lookup(request):
        #         return qs.none(), use_distinct
        #     return qs, use_distinct

        # try:
        #     student_pk = int(student_id)
        # except (TypeError, ValueError):
        #     return qs, use_distinct

        # student = Student.objects.filter(pk=student_pk).first()
        # if not student:
        #     return qs.none(), use_distinct

        # qs = qs.filter(curriculum_course__course__in=student.allowed_crss())
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
    def curri_crs_display(self, obj: Section) -> str:
        """Return the curriculum course label."""
        return str(obj.curriculum_course)

    @admin.display(description="Credits")
    def credit_hours(self, obj: Section) -> int:
        """Return credit hours for this section's curriculum_course."""
        return obj.curriculum_course.credit_hours_id or 3

    @admin.display(description="Curriculum", ordering="curriculum_course__curriculum")
    def curri_display(self, obj: Section) -> str:
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
