"""Admin configuration for registry models."""

from typing import TypeAlias, cast

from django import forms
from django.contrib import admin
from django.db.models import QuerySet
from django.urls import path
from import_export.admin import ImportExportModelAdmin

from app.people.models.student import Student
from app.registry.models.document import DocumentStatus, DocumentType

# from app.registry.admin.filters import GradeSectionFilter
# from app.registry.admin.views import SectioGradeValueerAutocomplete
from app.registry.models.grade import Grade, GradeValue
from app.registry.admin.filters import GradeStudentFilter
from app.registry.models.registration import Registration, RegistrationStatus
from app.registry.models.transcript import TranscriptRequest, TranscriptRequestStatus
from app.timetable.admin.filters import (
    SectionBySemesterFilter,
    SemesterFilterAC,
)
from app.timetable.admin.views import SectionBySemesterAutocomplete
from app.timetable.models.section import Section
from simple_history.admin import SimpleHistoryAdmin
from guardian.admin import GuardedModelAdmin
from app.shared.admin.mixins import ScopedAutocompleteAdminMixin

SectionQueryT: TypeAlias = QuerySet[Section]


def _section_queryset_for_student(student: Student | None) -> SectionQueryT:
    """Return sections scoped to a student or an empty queryset."""
    qs = Section.objects.select_related(
        "semester",
        "curriculum_course__course",
        "curriculum_course__curriculum",
    ).order_by("-semester__start_date", "curriculum_course__course__short_code")
    if not student:
        return qs.none()
    return qs.filter(curriculum_course__course__in=student.allowed_courses())


def _resolve_request_student(request) -> Student | None:
    """Resolve a student from request data or the current registration."""
    student_id = request.POST.get("student") or request.GET.get("student")
    if student_id:
        try:
            student_pk = int(student_id)
        except (TypeError, ValueError):
            return None
        return Student.objects.filter(pk=student_pk).first()
    resolver_match = getattr(request, "resolver_match", None)
    object_id = getattr(resolver_match, "kwargs", {}).get("object_id")
    if not object_id:
        return None
    registration = (
        Registration.objects.select_related("student").filter(pk=object_id).first()
    )
    return registration.student if registration else None


class RegistrationAdminForm(forms.ModelForm):
    """Admin form for Registration that scopes sections to the selected student."""

    class Meta:
        model = Registration
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        student = self._resolve_student()
        section_field = self.fields.get("section")
        if section_field is not None and isinstance(
            section_field, forms.ModelChoiceField
        ):
            section_field.queryset = _section_queryset_for_student(student)
            section_field.widget.attrs["data-student-field"] = "id_student"
            section_field.help_text = "Select a student first to load available sections."
        status_field = self.fields.get("status")
        if status_field is not None and not getattr(self.instance, "pk", None):
            status_field.initial = RegistrationStatus.get_default()

    def _resolve_student(self) -> Student | None:
        """Return the selected student from bound data or the instance."""
        student_id = (
            self.data.get("student")
            or self.initial.get("student")
            or getattr(self.instance, "student_id", None)
        )
        if not student_id:
            return None
        try:
            student_pk = int(student_id)
        except (TypeError, ValueError):
            return None
        return Student.objects.filter(pk=student_pk).first()

    def clean(self):
        """Ensure section selection is consistent with the selected student."""
        cleaned: dict[str, object] = super().clean() or {}
        student = cleaned.get("student")
        section = cleaned.get("section")
        if not student:
            if section:
                self.add_error("section", "Select a student before choosing a section.")
            return cleaned
        if section:
            student_obj = cast(Student, student)
            section_obj = cast(Section, section)
            allowed_courses = student_obj.allowed_courses()
            if not allowed_courses.filter(
                pk=section_obj.curriculum_course.course_id
            ).exists():
                self.add_error(
                    "section",
                    "Selected section is not available for this student.",
                )
        return cleaned


@admin.register(GradeValue)
class GradeValueAdmin(SimpleHistoryAdmin, ImportExportModelAdmin, GuardedModelAdmin):
    """Admin interface for registry.models.GradeValues.

    Describe the different grades types
    """

    list_display = ("number", "code", "description")
    search_fields = ("code", "description")


@admin.register(Grade)
class GradeAdmin(
    ScopedAutocompleteAdminMixin,
    SimpleHistoryAdmin,
    ImportExportModelAdmin,
    GuardedModelAdmin,
):
    """Admin interface for :class:~app.registry.models.Grade.

    Shows student, section and grade fields in the list view with autocomplete
    lookups for student and section.
    """

    date_hierarchy = "graded_on"
    list_display = (
        "student",
        # "grade_code",
        "section",
        "value__description",
        "section__semester",
        # "graded_on",
    )
    # list_filter = ['section__semester', GradeSectionFilter]
    list_filter = [SemesterFilterAC, SectionBySemesterFilter, GradeStudentFilter]
    autocomplete_fields = ("student", "section", "value")
    list_select_related = ("student__user", "section__semester", "value")
    search_fields = (
        "student__student_id",
        "student__long_name",
        "student__user__first_name",
        "student__user__last_name",
        "student__user__username",
        "section__semester__academic_year__code",
        "section__semester__academic_year__long_name",
        "section__semester__number",
        "section__curriculum_course__course__short_code",
    )

    def get_urls(self):
        """Returns urls."""
        urls = super().get_urls()
        custom = [
            path(
                "section_by_semester_autocomplete/",
                self.admin_site.admin_view(
                    SectionBySemesterAutocomplete.as_view(model_admin=self)
                ),
                name="section_by_semester_autocomplete",
            )
        ]
        return custom + urls

    @admin.display(description="Code")
    def grade_code(self, obj):
        """Display the letter grade in uppercase."""
        return (obj.value.code if obj.value else "").upper()


@admin.register(Registration)
class RegistrationAdmin(
    ScopedAutocompleteAdminMixin,
    SimpleHistoryAdmin,
    ImportExportModelAdmin,
    GuardedModelAdmin,
):
    """Allow students to register only for eligible sections."""

    form = RegistrationAdminForm
    list_display = ("student", "section", "status", "date_registered")
    autocomplete_fields = ("student", "section")
    search_fields = (
        "student__student_id",
        "section__curriculum_course__course__code",
        "section__number",
    )
    list_filter = (SemesterFilterAC,)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Override the form to limit sections to the student's curriculum_course."""
        if db_field.name == "section":
            student = _resolve_request_student(request)
            if student:
                kwargs["queryset"] = _section_queryset_for_student(student)
            else:
                kwargs["queryset"] = Section.objects.none()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    class Media:
        js = ("registry/js/registration_admin.js",)


@admin.register(TranscriptRequest)
class TranscriptRequestAdmin(
    ScopedAutocompleteAdminMixin, SimpleHistoryAdmin, GuardedModelAdmin
):
    """Allow students to request grade transcripts."""

    list_display = ("student", "status", "requested_at", "purpose")
    autocomplete_fields = ("student", "status")
    search_fields = ("student", "status")
    # > See how I can make this a AC field and limit the number of semester to the used semesters
    list_filter = (SemesterFilterAC,)


@admin.register(DocumentStatus, DocumentType, RegistrationStatus, TranscriptRequestStatus)
class CurriculumStatusAdmin(admin.ModelAdmin):
    """Lookup admin for CurriculumStatus."""

    search_fields = ("code", "label")
    list_display = ("label",)
