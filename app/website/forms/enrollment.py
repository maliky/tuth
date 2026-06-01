"""Portal-native enrollment forms."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, TypeAlias, TypedDict, cast

from django import forms
from django.contrib.auth.models import User
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.forms.renderers import BaseRenderer
from django.forms.utils import ErrorList
from django.utils.text import slugify
from django.utils.datastructures import MultiValueDict

from app.academics.models.curriculum import Curriculum
from app.people.models.student import Student
from app.people.models.student_curriculum_enrollment import set_primary_std_curri_enroll
from app.timetable.models.semester import Semester

StudentOptT: TypeAlias = Student | None


class StudentIntakeDataT(TypedDict):
    """Cleaned student intake values used to persist a portal profile."""

    student_id: str
    first_name: str
    last_name: str
    email: str
    primary_curriculum: Curriculum
    entry_semester: Semester | None
    last_enrolled_semester: Semester | None


class StudentIntakeForm(forms.Form):
    """Minimal portal form for enrollment staff to create or update a student."""

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
    last_name = forms.CharField(
        label="Last name",
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    email = forms.EmailField(
        label="Email",
        required=False,
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "Tusis can generate one if blank",
            }
        ),
    )
    primary_curriculum = forms.ModelChoiceField(
        label="Primary curriculum",
        queryset=Curriculum.objects.order_by("short_name"),
        widget=forms.Select(attrs={"class": "form-select"}),
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
            return

        self.fields["student_id"].initial = student.student_id
        self.fields["first_name"].initial = student.user.first_name
        self.fields["last_name"].initial = student.user.last_name
        self.fields["email"].initial = student.user.email
        self.fields["primary_curriculum"].initial = student.primary_curriculum
        self.fields["entry_semester"].initial = student.entry_semester
        self.fields["last_enrolled_semester"].initial = student.last_enrolled_semester

    def clean_student_id(self) -> str:
        """Normalize manual student IDs without forcing one."""
        value = str(self.cleaned_data.get("student_id") or "").strip().upper()
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
        "last_name": cast(str, form.cleaned_data["last_name"]).strip(),
        "email": cast(str, form.cleaned_data.get("email") or "").strip(),
        "primary_curriculum": cast(Curriculum, form.cleaned_data["primary_curriculum"]),
        "entry_semester": cast(Semester | None, form.cleaned_data["entry_semester"]),
        "last_enrolled_semester": cast(
            Semester | None,
            form.cleaned_data["last_enrolled_semester"],
        ),
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

    if data["student_id"]:
        student.student_id = data["student_id"]
    student.entry_semester = data["entry_semester"]
    student.last_enrolled_semester = (
        data["last_enrolled_semester"] or data["entry_semester"]
    )
    student.save()
    set_primary_std_curri_enroll(
        student,
        data["primary_curriculum"],
        entry_semester_id=student.entry_semester_id,
        is_active=True,
    )
    return student
