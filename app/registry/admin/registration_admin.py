"""Admin configuration for registry models."""

from typing import Optional, TypeAlias, cast

from django import forms
from django.contrib import admin
from django.db.models import Case, CharField, Count, F, QuerySet, Value, When
from django.db.models.functions import Cast, Concat
from django.urls import path, reverse
from django.utils.html import format_html
from django.contrib.admin.widgets import FilteredSelectMultiple
from import_export.admin import ImportExportModelAdmin

from app.people.models.student import Student
from app.registry.models.document import DocStatus, DocType

# from app.registry.admin.filters import GradeSecFlt
# from app.registry.admin.views import SectioGradeValueerAutocomplete
from app.registry.models.grade import Grade, GradeValue
from app.registry.admin.resources import GradeResource
from app.registry.admin.filters import GradeStdFlt
from app.registry.models.registration import Registration, RegistrationStatus
from app.registry.models.transcript import TranscriptRequest, TranscriptRequestStatus
from app.timetable.admin.filters import (
    SecBySemFlt,
    SemFltAC,
)
from app.timetable.admin.views import SecBySemAutocomplete
from app.timetable.models.semester import Semester
from app.timetable.models.section import Section
from simple_history.admin import SimpleHistoryAdmin
from guardian.admin import GuardedModelAdmin
from app.shared.admin.mixins import ScopedAutocompleteAdminMixin

SectionQueryT: TypeAlias = QuerySet[Section]
SemesterT: TypeAlias = Semester


def _open_regio_sem() -> Optional[SemesterT]:
    """Return the single semester open for registration."""
    semester, _ = Semester.regio_open_sem()
    return semester


def _sec_queryset_for_std(student: Optional[Student]) -> SectionQueryT:
    """Return sections scoped to a student or an empty queryset."""
    qs = Section.objects.select_related(
        "semester",
        "curriculum_course__course",
        "curriculum_course__curriculum",
    ).order_by("-semester__start_date", "curriculum_course__course__short_code")
    open_semester = _open_regio_sem()
    if not open_semester:
        return qs.none()
    if not student:
        return qs.none()
    return qs.filter(
        semester=open_semester,
        curriculum_course__course__in=student.allowed_crss(),
    )


def _available_secs_for_std(student: Student | None) -> SectionQueryT:
    """Return sections eligible for new registrations for the student."""
    qs = _sec_queryset_for_std(student)
    if not student:
        return qs
    registered_ids = Registration.objects.filter(student=student).values_list(
        "section_id",
        flat=True,
    )
    if not registered_ids:
        return qs
    return qs.exclude(id__in=registered_ids)


def _resolve_request_std(request) -> Optional[Student]:
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


class RegioAdminForm(forms.ModelForm):
    """Admin form for Registration that scopes sections to the selected student."""

    class Meta:
        model = Registration
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        student = self._resolve_std()
        section_field = self.fields.get("section")
        if section_field is not None and isinstance(
            section_field, forms.ModelChoiceField
        ):
            section_field.queryset = _sec_queryset_for_std(student)
            section_field.widget.attrs["data-student-field"] = "id_student"
            section_field.help_text = "Select a student first to load available sections."

        status_field = self.fields.get("status")
        if status_field is not None and not getattr(self.instance, "pk", None):
            status_field.initial = RegistrationStatus.get_dft()

    def _resolve_std(self) -> Optional[Student]:
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
            allowed_crss = student_obj.allowed_crss()
            if not allowed_crss.filter(
                pk=section_obj.curriculum_course.course_id
            ).exists():
                self.add_error(
                    "section",
                    "Selected section is not available for this student.",
                )
        return cleaned


class RegioBulkAddForm(forms.ModelForm):
    """Admin form for adding multiple registrations at once."""

    sections = forms.ModelMultipleChoiceField(
        queryset=Section.objects.none(),
        required=True,
        widget=FilteredSelectMultiple("Sections", False),
    )

    class Meta:
        model = Registration
        fields = ("student", "sections", "status")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        student = self._resolve_std()
        sections_field = self.fields.get("sections")
        if sections_field is not None and isinstance(
            sections_field, forms.ModelMultipleChoiceField
        ):
            sections_field.queryset = _available_secs_for_std(student)
            sections_field.help_text = (
                "Select a student first to load available sections."
            )
        status_field = self.fields.get("status")
        if status_field is not None and not getattr(self.instance, "pk", None):
            status_field.initial = RegistrationStatus.get_dft()

    def _resolve_std(self) -> Student | None:
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
        """Ensure selected sections are available for the selected student."""
        cleaned: dict[str, object] = super().clean() or {}
        student = cleaned.get("student")
        sections = list(cast(list[Section], cleaned.get("sections") or []))
        if not student:
            if sections:
                self.add_error("sections", "Select a student before choosing sections.")
            return cleaned
        if not sections:
            self.add_error("sections", "Select at least one section.")
            return cleaned
        student_obj = cast(Student, student)
        available_ids = set(
            _available_secs_for_std(student_obj).values_list("id", flat=True)
        )
        invalid = [section for section in sections if section.pk not in available_ids]
        if invalid:
            self.add_error(
                "sections",
                "Selected sections are not available for this student.",
            )
            return cleaned
        existing_ids = set(
            Registration.objects.filter(
                student=student_obj,
                section__in=sections,
            ).values_list("section_id", flat=True)
        )
        sections_to_create = [
            section for section in sections if section.pk not in existing_ids
        ]
        if not sections_to_create:
            self.add_error(
                "sections",
                "All selected sections are already registered for this student.",
            )
            return cleaned
        cleaned["sections_to_create"] = sections_to_create
        return cleaned


@admin.register(Registration)
class RegioAdmin(
    ScopedAutocompleteAdminMixin,
    SimpleHistoryAdmin,
    ImportExportModelAdmin,
    GuardedModelAdmin,
):
    """Allow students to register only for eligible sections."""

    form = RegioAdminForm
    list_display = ("student", "section", "status", "date_registered")
    autocomplete_fields = ("student", "section")
    search_fields = (
        "student__student_id",
        "section__curriculum_course__course__code",
        "section__number",
    )
    list_filter = (SemFltAC,)

    def get_form(self, request, obj=None, **kwargs):
        """Select a bulk-add form for new registrations."""
        if obj is None:
            kwargs["form"] = RegioBulkAddForm
        return super().get_form(request, obj, **kwargs)

    def save_model(self, request, obj, form, change):
        """Create one or more registrations when bulk sections are provided."""
        if not change and isinstance(form, RegioBulkAddForm):
            student = cast(Student | None, form.cleaned_data.get("student"))
            sections_to_create = list(
                cast(
                    list[Section],
                    form.cleaned_data.get("sections_to_create") or [],
                )
            )
            status = form.cleaned_data.get("status") or RegistrationStatus.get_dft()
            if not student or not sections_to_create:
                return
            primary_section = sections_to_create[0]
            obj.student = student
            obj.section = primary_section
            obj.status = status
            super().save_model(request, obj, form, change)
            created_count = 1
            skipped_count = 0
            for section in sections_to_create[1:]:
                _, created = Registration.objects.get_or_create(
                    student=student,
                    section=section,
                    defaults={"status": status},
                )
                if created:
                    created_count += 1
                else:
                    skipped_count += 1
            total_selected = len(form.cleaned_data.get("sections") or [])
            skipped_count += max(total_selected - created_count - skipped_count, 0)
            if created_count:
                self.message_user(
                    request,
                    (
                        f"Created {created_count} registration(s). "
                        f"Skipped {skipped_count} existing registration(s)."
                    ),
                )
            return
        super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Override the form to limit sections to the student's curriculum_course."""
        if db_field.name == "section":
            student = _resolve_request_std(request)
            if student:
                kwargs["queryset"] = _sec_queryset_for_std(student)
            else:
                kwargs["queryset"] = Section.objects.none()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    class Media:
        js = ("build/registry/static/registry/js/registration_admin.js",)


__all__ = [
    "RegioAdmin",
    "RegioAdminForm",
    "RegioBulkAddForm",
    "_available_secs_for_std",
    "_open_regio_sem",
    "_resolve_request_std",
    "_sec_queryset_for_std",
]
