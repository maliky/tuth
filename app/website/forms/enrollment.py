"""Portal-native enrollment forms."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from typing import Any, TypeAlias, TypedDict, cast

from django import forms
from django.contrib.auth.models import User
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.forms.renderers import BaseRenderer
from django.forms.utils import ErrorList
from django.utils.text import slugify
from django.utils.datastructures import MultiValueDict

from app.academics.constants import MAX_STUDENT_CREDITS
from app.academics.models.curriculum import Curriculum
from app.people.models.student import Student
from app.people.models.student_curriculum_enrollment import set_primary_std_curri_enroll
from app.shared.student_ids import canonical_student_id
from app.timetable.models.semester import Semester

StudentOptT: TypeAlias = Student | None


class StudentIntakeDataT(TypedDict):
    """Cleaned student intake values used to persist a portal profile."""

    student_id: str
    first_name: str
    middle_name: str
    last_name: str
    prefix_name: str
    suffix_name: str
    email: str
    primary_curriculum: Curriculum
    entry_semester: Semester | None
    last_enrolled_semester: Semester | None
    max_credit_hours: int
    phone_number: str
    physical_address: str
    birth_date: date | None
    birth_place: str
    gender: str
    nationality: str
    origin_county: str
    marital_status: str
    last_school_attended: str
    reason_for_leaving: str
    father_name: str
    father_address: str
    mother_name: str
    mother_address: str
    emergency_contact: str


class StudentIntakeForm(forms.Form):
    """Portal form for enrollment staff to create or update a student profile."""

    student_id = forms.CharField(
        label="Student ID",
        required=False,
        max_length=20,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Leave blank to auto-generate",
            }
        ),
    )
    first_name = forms.CharField(
        label="First name",
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    middle_name = forms.CharField(
        label="Middle name",
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    last_name = forms.CharField(
        label="Last name",
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    prefix_name = forms.CharField(
        label="Prefix",
        required=False,
        max_length=255,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Miss., Mr., Dr."}
        ),
    )
    suffix_name = forms.CharField(
        label="Suffix",
        required=False,
        max_length=255,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Jr., Sr., PhD"}
        ),
    )
    email = forms.EmailField(
        label="Email",
        required=False,
        help_text="Leave blank to generate one, e.g. maria.kollie.stud@tubmanu.edu.lr.",
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "Tusis can generate one if blank",
            }
        ),
    )
    primary_curriculum = forms.ModelChoiceField(
        label="Program / Curriculum",
        queryset=Curriculum.objects.select_related("college").order_by(
            "college__code", "long_name", "short_name"
        ),
        widget=forms.Select(
            attrs={
                "class": "form-select",
                "data-curriculum-autocomplete": "true",
            }
        ),
    )
    entry_semester = forms.ModelChoiceField(
        label="Entry semester",
        queryset=Semester.objects.select_related("academic_year").order_by(
            "-academic_year__start_date",
            "-number",
        ),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    max_credit_hours = forms.IntegerField(
        label="Maximum credits",
        min_value=0,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )
    phone_number = forms.CharField(
        label="Phone",
        required=False,
        max_length=128,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    physical_address = forms.CharField(
        label="Physical address",
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )
    birth_date = forms.DateField(
        label="Date of birth",
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    birth_place = forms.CharField(
        label="Birth place",
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    gender = forms.ChoiceField(
        label="Gender",
        choices=(("", "---------"), ("f", "Female"), ("m", "Male")),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    nationality = forms.CharField(
        label="Nationality",
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    origin_county = forms.CharField(
        label="Origin county",
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    marital_status = forms.CharField(
        label="Marital status",
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    last_school_attended = forms.CharField(
        label="Last school attended",
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    reason_for_leaving = forms.CharField(
        label="Reason for leaving",
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )
    father_name = forms.CharField(
        label="Father name",
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    father_address = forms.CharField(
        label="Father address",
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )
    mother_name = forms.CharField(
        label="Mother name",
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    mother_address = forms.CharField(
        label="Mother address",
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )
    emergency_contact = forms.CharField(
        label="Emergency contact",
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    last_enrolled_semester = forms.ModelChoiceField(
        label="Current semester",
        queryset=Semester.objects.select_related("academic_year").order_by(
            "-academic_year__start_date",
            "-number",
        ),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(
        self,
        data: Mapping[str, Any] | None = None,
        files: MultiValueDict[str, UploadedFile] | None = None,
        auto_id: bool | str = "id_%s",
        prefix: str | None = None,
        initial: dict[str, Any] | None = None,
        error_class: type[ErrorList] = ErrorList,
        label_suffix: str | None = None,
        empty_permitted: bool = False,
        field_order: Iterable[str] | None = None,
        use_required_attribute: bool | None = None,
        renderer: BaseRenderer | None = None,
        *,
        student: StudentOptT = None,
    ) -> None:
        """Seed the form from an existing student when editing."""
        super().__init__(
            data=data,
            files=files,
            auto_id=auto_id,
            prefix=prefix,
            initial=initial,
            error_class=error_class,
            label_suffix=label_suffix,
            empty_permitted=empty_permitted,
            field_order=field_order,
            use_required_attribute=use_required_attribute,
            renderer=renderer,
        )
        self.student = student
        if student is None:
            current_semester = Semester.get_current_sem()
            self.fields["entry_semester"].initial = current_semester
            self.fields["last_enrolled_semester"].initial = current_semester
            self.fields["primary_curriculum"].initial = Curriculum.get_dft()
            self.fields["max_credit_hours"].initial = MAX_STUDENT_CREDITS
            return

        self.fields["student_id"].initial = student.student_id
        self.fields["first_name"].initial = student.user.first_name
        self.fields["middle_name"].initial = student.middle_name
        self.fields["last_name"].initial = student.user.last_name
        self.fields["prefix_name"].initial = student.prefix_name
        self.fields["suffix_name"].initial = student.suffix_name
        self.fields["email"].initial = student.user.email
        self.fields["primary_curriculum"].initial = student.primary_curriculum
        self.fields["entry_semester"].initial = student.entry_semester
        self.fields["last_enrolled_semester"].initial = student.last_enrolled_semester
        self.fields["max_credit_hours"].initial = student.max_credit_hours
        self.fields["phone_number"].initial = student.phone_number
        self.fields["physical_address"].initial = student.physical_address
        self.fields["birth_date"].initial = student.birth_date
        self.fields["birth_place"].initial = student.birth_place
        self.fields["gender"].initial = student.gender
        self.fields["nationality"].initial = student.nationality
        self.fields["origin_county"].initial = student.origin_county
        self.fields["marital_status"].initial = student.marital_status
        self.fields["last_school_attended"].initial = student.last_school_attended
        self.fields["reason_for_leaving"].initial = student.reason_for_leaving
        self.fields["father_name"].initial = student.father_name
        self.fields["father_address"].initial = student.father_address
        self.fields["mother_name"].initial = student.mother_name
        self.fields["mother_address"].initial = student.mother_address
        self.fields["emergency_contact"].initial = student.emergency_contact

    def clean_student_id(self) -> str:
        """Normalize manual student IDs without forcing one."""
        value = canonical_student_id(str(self.cleaned_data.get("student_id") or ""))
        if not value:
            return ""
        qs = Student.objects.filter(student_id__iexact=value)
        if self.student is not None:
            qs = qs.exclude(pk=self.student.pk)
        if qs.exists():
            raise forms.ValidationError("That student ID is already assigned.")
        return value


def _unique_student_username(first_name: str, last_name: str, student_id: str) -> str:
    """Return a stable username candidate for a new student account."""
    seed = student_id or f"{first_name}.{last_name}"
    base = slugify(seed, allow_unicode=False).replace("-", "_")[:42] or "student"
    username = base
    suffix = 1
    while User.objects.filter(username=username).exists():
        suffix += 1
        username = f"{base}_{suffix}"
    return username


def _student_intake_data(form: StudentIntakeForm) -> StudentIntakeDataT:
    """Narrow cleaned form values into a typed payload."""
    return {
        "student_id": cast(str, form.cleaned_data["student_id"]),
        "first_name": cast(str, form.cleaned_data["first_name"]).strip(),
        "middle_name": cast(str, form.cleaned_data.get("middle_name") or "").strip(),
        "last_name": cast(str, form.cleaned_data["last_name"]).strip(),
        "prefix_name": cast(str, form.cleaned_data.get("prefix_name") or "").strip(),
        "suffix_name": cast(str, form.cleaned_data.get("suffix_name") or "").strip(),
        "email": cast(str, form.cleaned_data.get("email") or "").strip(),
        "primary_curriculum": cast(Curriculum, form.cleaned_data["primary_curriculum"]),
        "entry_semester": cast(Semester | None, form.cleaned_data["entry_semester"]),
        "last_enrolled_semester": cast(
            Semester | None,
            form.cleaned_data["last_enrolled_semester"],
        ),
        "max_credit_hours": cast(
            int,
            form.cleaned_data.get("max_credit_hours") or MAX_STUDENT_CREDITS,
        ),
        "phone_number": cast(str, form.cleaned_data.get("phone_number") or "").strip(),
        "physical_address": cast(
            str, form.cleaned_data.get("physical_address") or ""
        ).strip(),
        "birth_date": cast(date | None, form.cleaned_data.get("birth_date")),
        "birth_place": cast(str, form.cleaned_data.get("birth_place") or "").strip(),
        "gender": cast(str, form.cleaned_data.get("gender") or "").strip(),
        "nationality": cast(str, form.cleaned_data.get("nationality") or "").strip(),
        "origin_county": cast(str, form.cleaned_data.get("origin_county") or "").strip(),
        "marital_status": cast(
            str, form.cleaned_data.get("marital_status") or ""
        ).strip(),
        "last_school_attended": cast(
            str, form.cleaned_data.get("last_school_attended") or ""
        ).strip(),
        "reason_for_leaving": cast(
            str, form.cleaned_data.get("reason_for_leaving") or ""
        ).strip(),
        "father_name": cast(str, form.cleaned_data.get("father_name") or "").strip(),
        "father_address": cast(
            str, form.cleaned_data.get("father_address") or ""
        ).strip(),
        "mother_name": cast(str, form.cleaned_data.get("mother_name") or "").strip(),
        "mother_address": cast(
            str, form.cleaned_data.get("mother_address") or ""
        ).strip(),
        "emergency_contact": cast(
            str, form.cleaned_data.get("emergency_contact") or ""
        ).strip(),
    }


@transaction.atomic
def save_student_intake(
    form: StudentIntakeForm,
    student: StudentOptT = None,
) -> Student:
    """Create or update a student from the portal-native enrollment form."""
    data = _student_intake_data(form)
    if student is None:
        username = _unique_student_username(
            data["first_name"],
            data["last_name"],
            data["student_id"],
        )
        user = User.objects.create_user(
            username=username,
            first_name=data["first_name"],
            last_name=data["last_name"],
            email=data["email"],
        )
        user.set_unusable_password()
        user.save(update_fields=["password"])
        student = Student(user=user)
    else:
        user = student.user
        user.first_name = data["first_name"]
        user.last_name = data["last_name"]
        user.email = data["email"]
        user.save(update_fields=["first_name", "last_name", "email"])
        # Student.save() only fills an empty name; portal edits must refresh it.
        student.long_name = ""

    if data["student_id"]:
        student.student_id = data["student_id"]
    student.entry_semester = data["entry_semester"]
    student.last_enrolled_semester = (
        data["last_enrolled_semester"] or data["entry_semester"]
    )
    student.middle_name = data["middle_name"]
    student.prefix_name = data["prefix_name"]
    student.suffix_name = data["suffix_name"]
    student.max_credit_hours = data["max_credit_hours"]
    student.phone_number = data["phone_number"]
    student.physical_address = data["physical_address"]
    student.birth_date = data["birth_date"]
    student.birth_place = data["birth_place"]
    student.gender = data["gender"]
    student.nationality = data["nationality"]
    student.origin_county = data["origin_county"]
    student.marital_status = data["marital_status"]
    student.last_school_attended = data["last_school_attended"]
    student.reason_for_leaving = data["reason_for_leaving"]
    student.father_name = data["father_name"]
    student.father_address = data["father_address"]
    student.mother_name = data["mother_name"]
    student.mother_address = data["mother_address"]
    student.emergency_contact = data["emergency_contact"]
    student.save()
    set_primary_std_curri_enroll(
        student,
        data["primary_curriculum"],
        entry_semester_id=student.entry_semester_id,
        is_active=True,
    )
    return student
