"""Forms for public applicant enrollment requests and staff review."""

from __future__ import annotations

from string import Formatter
from typing import Any, TypeAlias, cast

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import QuerySet

from app.academics.career_scope import CareerModeT
from app.academics.choices import AcademicCareer
from app.academics.models.curriculum import Curriculum
from app.people.models.enrollment_application import (
    EnrollmentApplication,
    EnrollmentApplicationDoc,
    EnrollmentApplicationStatus,
    EnrollmentEmailTemplate,
)
from app.people.models.student import Student
from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.semester import Semester
from app.website.services.enrollment_applications import active_application_exists
from app.website.services.semester_scope import semester_queryset_for_career

FieldAttrsT: TypeAlias = dict[str, str]


BASE_INPUT_ATTRS: FieldAttrsT = {"class": "form-control"}
BASE_SELECT_ATTRS: FieldAttrsT = {"class": "form-select"}
EMAIL_TEMPLATE_FIELDS = frozenset(
    {
        "applicant_name",
        "career",
        "code",
        "program",
        "username",
        "verification_url",
    }
)


def _validate_email_template(
    value: str,
    *,
    required: tuple[str, ...] = (),
) -> str:
    """Validate editable email text against the supported placeholders."""
    formatter = Formatter()
    try:
        fields = {
            field_name
            for _literal, field_name, _format_spec, _conversion in formatter.parse(value)
            if field_name
        }
    except ValueError as exc:
        raise ValidationError("Template formatting is invalid.") from exc
    unknown = sorted(fields - EMAIL_TEMPLATE_FIELDS)
    if unknown:
        raise ValidationError(f"Unsupported placeholders: {', '.join(unknown)}.")
    missing = [field_name for field_name in required if field_name not in fields]
    if missing:
        placeholders = ", ".join(f"{{{field_name}}}" for field_name in missing)
        raise ValidationError(f"The template must include: {placeholders}.")
    try:
        formatter.vformat(
            value,
            (),
            {field_name: "value" for field_name in EMAIL_TEMPLATE_FIELDS},
        )
    except (AttributeError, IndexError, KeyError, ValueError) as exc:
        raise ValidationError("Template formatting is invalid.") from exc
    return value


class ProgramChoiceField(forms.ModelChoiceField):
    """Display curricula as public-facing program names."""

    def label_from_instance(self, obj: Curriculum) -> str:
        """Return the curriculum long name, falling back to the code."""
        return str(obj.long_name or obj.short_name)


class AcademicYearChoiceField(forms.ModelChoiceField):
    """Display academic years without exposing semester internals."""

    def label_from_instance(self, obj: AcademicYear) -> str:
        """Return the readable academic year label."""
        return str(obj.long_name or obj.code)


def _academic_years_for_career(career: CareerModeT) -> QuerySet[AcademicYear]:
    """Return academic years that have semesters for the selected career."""
    semester_ids = list(
        semester_queryset_for_career(
            career,
            Semester.objects.select_related("academic_year"),
        )
        .values_list("academic_year_id", flat=True)
        .distinct()
    )
    return AcademicYear.objects.filter(id__in=semester_ids).order_by("-start_date")


def _entry_semester_for_year(
    *,
    academic_year: AcademicYear,
    career: CareerModeT,
) -> Semester | None:
    """Return the first configured semester for an applicant academic year."""
    return (
        semester_queryset_for_career(
            career,
            Semester.objects.filter(academic_year=academic_year).select_related(
                "academic_year"
            ),
        )
        .order_by("number")
        .first()
    )


class EnrollmentApplicationBaseForm(forms.ModelForm):
    """Shared applicant profile fields and career scoping."""

    desired_curriculum = ProgramChoiceField(
        label="Desired program",
        queryset=Curriculum.objects.none(),
        widget=forms.Select(attrs=BASE_SELECT_ATTRS),
    )
    desired_academic_year = AcademicYearChoiceField(
        label="Academic year",
        queryset=AcademicYear.objects.none(),
        widget=forms.Select(attrs=BASE_SELECT_ATTRS),
    )

    class Meta:
        model = EnrollmentApplication
        fields: tuple[str, ...] = (
            "personal_email",
            "academic_career",
            "desired_curriculum",
            "prefix_name",
            "first_name",
            "middle_name",
            "last_name",
            "suffix_name",
            "phone_number",
            "physical_address",
            "birth_date",
            "birth_place",
            "gender",
            "nationality",
            "origin_county",
            "marital_status",
            "last_school_attended",
            "reason_for_leaving",
            "father_name",
            "father_address",
            "mother_name",
            "mother_address",
            "emergency_contact",
        )
        widgets = {
            "personal_email": forms.EmailInput(attrs=BASE_INPUT_ATTRS),
            "academic_career": forms.Select(attrs=BASE_SELECT_ATTRS),
            "prefix_name": forms.TextInput(attrs=BASE_INPUT_ATTRS),
            "first_name": forms.TextInput(attrs=BASE_INPUT_ATTRS),
            "middle_name": forms.TextInput(attrs=BASE_INPUT_ATTRS),
            "last_name": forms.TextInput(attrs=BASE_INPUT_ATTRS),
            "suffix_name": forms.TextInput(attrs=BASE_INPUT_ATTRS),
            "phone_number": forms.TextInput(attrs=BASE_INPUT_ATTRS),
            "physical_address": forms.Textarea(attrs={**BASE_INPUT_ATTRS, "rows": "2"}),
            "birth_date": forms.DateInput(attrs={**BASE_INPUT_ATTRS, "type": "date"}),
            "birth_place": forms.TextInput(attrs=BASE_INPUT_ATTRS),
            "gender": forms.Select(attrs=BASE_SELECT_ATTRS),
            "nationality": forms.TextInput(attrs=BASE_INPUT_ATTRS),
            "origin_county": forms.TextInput(attrs=BASE_INPUT_ATTRS),
            "marital_status": forms.TextInput(attrs=BASE_INPUT_ATTRS),
            "last_school_attended": forms.TextInput(attrs=BASE_INPUT_ATTRS),
            "reason_for_leaving": forms.Textarea(attrs={**BASE_INPUT_ATTRS, "rows": "2"}),
            "father_name": forms.TextInput(attrs=BASE_INPUT_ATTRS),
            "father_address": forms.Textarea(attrs={**BASE_INPUT_ATTRS, "rows": "2"}),
            "mother_name": forms.TextInput(attrs=BASE_INPUT_ATTRS),
            "mother_address": forms.Textarea(attrs={**BASE_INPUT_ATTRS, "rows": "2"}),
            "emergency_contact": forms.TextInput(attrs=BASE_INPUT_ATTRS),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Scope programs and academic years to the selected career."""
        super().__init__(*args, **kwargs)
        career = self._selected_career()
        curriculum_field = cast(
            ProgramChoiceField,
            self.fields["desired_curriculum"],
        )
        curriculum_field.queryset = (
            Curriculum.objects.filter(academic_career=career, is_active=True)
            .select_related("college")
            .order_by("college__code", "long_name", "short_name")
        )
        year_field = cast(AcademicYearChoiceField, self.fields["desired_academic_year"])
        year_field.queryset = _academic_years_for_career(career)
        if self.instance.pk and self.instance.desired_entry_semester_id:
            year_field.initial = self.instance.desired_entry_semester.academic_year_id
        self.fields["academic_career"].initial = career

    def _selected_career(self) -> CareerModeT:
        """Return posted or initial career."""
        raw = ""
        if self.data:
            raw = str(self.data.get("academic_career") or "")
        if not raw and self.instance.pk:
            raw = self.instance.academic_career
        if raw == AcademicCareer.UNDERGRADUATE.value:
            return "undergraduate"
        return "graduate"

    def clean_personal_email(self) -> str:
        """Reject duplicate active applicant or student emails."""
        email = cast(str, self.cleaned_data["personal_email"]).strip().lower()
        active_statuses = [
            EnrollmentApplicationStatus.PENDING,
            EnrollmentApplicationStatus.VERIFIED,
            EnrollmentApplicationStatus.UNDER_REVIEW,
            EnrollmentApplicationStatus.APPROVED,
        ]
        qs = EnrollmentApplication.objects.filter(
            personal_email__iexact=email,
            status__in=active_statuses,
        )
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        student_conflict = Student.objects.filter(user__email__iexact=email).exists()
        if (
            qs.exists()
            or student_conflict
            or (not self.instance.pk and active_application_exists(email))
        ):
            raise forms.ValidationError("That email already has an active request.")
        return email

    def clean(self) -> dict[str, object]:
        """Ensure career and desired program match."""
        cleaned = dict(super().clean() or {})
        curriculum = cleaned.get("desired_curriculum")
        career = cleaned.get("academic_career")
        if isinstance(curriculum, Curriculum) and curriculum.academic_career != career:
            self.add_error("desired_curriculum", "Program does not match career track.")
        academic_year = cleaned.get("desired_academic_year")
        if isinstance(academic_year, AcademicYear) and isinstance(career, str):
            entry_semester = _entry_semester_for_year(
                academic_year=academic_year,
                career=cast(CareerModeT, career),
            )
            if entry_semester is None:
                self.add_error(
                    "desired_academic_year",
                    "No semester is configured for that academic year.",
                )
            else:
                cleaned["desired_entry_semester"] = entry_semester
        return cleaned

    def save(self, commit: bool = True) -> EnrollmentApplication:
        """Persist the selected academic year as the first entry semester."""
        application = cast(EnrollmentApplication, super().save(commit=False))
        entry_semester = self.cleaned_data.get("desired_entry_semester")
        if isinstance(entry_semester, Semester):
            application.desired_entry_semester = entry_semester
        if commit:
            application.save()
            self.save_m2m()
        return application


class EnrollmentApplicationForm(EnrollmentApplicationBaseForm):
    """Public form for applicants requesting enrollment."""

    class Meta(EnrollmentApplicationBaseForm.Meta):
        fields: tuple[str, ...] = (
            "personal_email",
            "academic_career",
            "desired_curriculum",
            "first_name",
            "last_name",
        )

    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs=BASE_INPUT_ATTRS),
    )
    password2 = forms.CharField(
        label="Confirm password",
        widget=forms.PasswordInput(attrs=BASE_INPUT_ATTRS),
    )

    def clean_password2(self) -> str:
        """Validate the confirmed applicant password."""
        password1 = str(self.cleaned_data.get("password1") or "")
        password2 = str(self.cleaned_data.get("password2") or "")
        if password1 != password2:
            raise forms.ValidationError("The two password fields did not match.")
        validate_password(password2)
        return password2


class ApplicantProfileForm(EnrollmentApplicationBaseForm):
    """Applicant self-service edit form after email verification."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Keep the already verified personal email immutable."""
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["personal_email"].disabled = True


class VerificationCodeForm(forms.Form):
    """Form for entering a six-digit email verification code."""

    code = forms.CharField(
        label="Verification code",
        min_length=6,
        max_length=6,
        widget=forms.TextInput(attrs={**BASE_INPUT_ATTRS, "inputmode": "numeric"}),
    )


class ApplicationDocumentForm(forms.ModelForm):
    """Upload one applicant document."""

    class Meta:
        model = EnrollmentApplicationDoc
        fields = ("document_type", "data_file")
        widgets = {
            "document_type": forms.Select(attrs=BASE_SELECT_ATTRS),
            "data_file": forms.ClearableFileInput(attrs=BASE_INPUT_ATTRS),
        }


class StaffApplicationReviewForm(forms.ModelForm):
    """Enrollment staff review controls."""

    class Meta:
        model = EnrollmentApplication
        fields = (
            "status",
            "documents_reviewed",
            "placement_exam_completed",
            "review_notes",
        )
        widgets = {
            "status": forms.Select(attrs=BASE_SELECT_ATTRS),
            "documents_reviewed": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "placement_exam_completed": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "review_notes": forms.Textarea(attrs={**BASE_INPUT_ATTRS, "rows": "4"}),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Keep conversion-only statuses out of ordinary review saves."""
        super().__init__(*args, **kwargs)
        allowed_statuses = {
            EnrollmentApplicationStatus.PENDING,
            EnrollmentApplicationStatus.VERIFIED,
            EnrollmentApplicationStatus.UNDER_REVIEW,
            EnrollmentApplicationStatus.REJECTED,
        }
        status_field = cast(forms.ChoiceField, self.fields["status"])
        status_field.choices = [
            choice
            for choice in EnrollmentApplicationStatus.choices
            if choice[0] in allowed_statuses
        ]


class EnrollmentEmailTemplateForm(forms.ModelForm):
    """Edit the verification email template."""

    class Meta:
        model = EnrollmentEmailTemplate
        fields = ("subject", "body")
        widgets = {
            "subject": forms.TextInput(attrs=BASE_INPUT_ATTRS),
            "body": forms.Textarea(attrs={**BASE_INPUT_ATTRS, "rows": "10"}),
        }

    def clean_subject(self) -> str:
        """Reject unsupported or malformed subject placeholders."""
        return _validate_email_template(cast(str, self.cleaned_data["subject"]))

    def clean_body(self) -> str:
        """Require placeholders needed for account verification."""
        return _validate_email_template(
            cast(str, self.cleaned_data["body"]),
            required=("code", "username"),
        )


class EnrollmentCommunicationForm(forms.Form):
    """Compose a communication to selected applicants."""

    subject = forms.CharField(
        max_length=255, widget=forms.TextInput(attrs=BASE_INPUT_ATTRS)
    )
    body = forms.CharField(widget=forms.Textarea(attrs={**BASE_INPUT_ATTRS, "rows": "6"}))
    selected_applications = forms.ModelMultipleChoiceField(
        queryset=EnrollmentApplication.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    send_to_filtered = forms.BooleanField(required=False)

    def __init__(
        self,
        *args: Any,
        queryset: QuerySet[EnrollmentApplication] | None = None,
        **kwargs: Any,
    ) -> None:
        """Inject the filtered applicant queryset used for recipient choices."""
        super().__init__(*args, **kwargs)
        if queryset is not None:
            selected_field = cast(
                forms.ModelMultipleChoiceField,
                self.fields["selected_applications"],
            )
            selected_field.queryset = queryset

    def clean(self) -> dict[str, object]:
        """Require either selected rows or the filtered-recipient option."""
        cleaned = dict(super().clean() or {})
        selected = cleaned.get("selected_applications")
        if not cleaned.get("send_to_filtered") and not selected:
            raise ValidationError("Select applicants or choose all filtered applicants.")
        return cleaned


__all__ = [
    "ApplicantProfileForm",
    "ApplicationDocumentForm",
    "EnrollmentApplicationForm",
    "EnrollmentCommunicationForm",
    "EnrollmentEmailTemplateForm",
    "StaffApplicationReviewForm",
    "VerificationCodeForm",
]
