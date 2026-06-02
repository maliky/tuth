"""Defines model forms for the people module."""

from app.academics.models.curriculum import Curriculum
from app.people.forms.base import PersonFormMixin
from app.people.models.donor import Donor
from app.people.models.staffs import Staff
from app.people.models.student import Student
from app.people.models.student_curriculum_enrollment import set_primary_std_curri_enroll
from app.shared.types import FieldT
from django import forms


class DonorForm(PersonFormMixin, forms.ModelForm):
    class Meta:
        model = Donor
        fields: FieldT = []


# class FacultyFrom(forms.ModelForm):
#     """Need a form to create a staff on the fly."""

#     None


class StaffForm(PersonFormMixin, forms.ModelForm):
    SPECIFIC_FIELDS = ("division", "department", "position", "employment_date")

    class Meta:
        model = Staff
        fields: FieldT = []


class StdForm(PersonFormMixin, forms.ModelForm):
    primary_curriculum = forms.ModelChoiceField(
        queryset=Curriculum.objects.order_by("short_name"),
        required=False,
        label="curriculum",
    )
    SPECIFIC_FIELDS = (
        "student_id",
        "primary_curriculum",
        "last_enrolled_semester",
        "entry_semester",
        "max_credit_hours",
        "last_school_attended",
        "reason_for_leaving",
        "father_name",
        "father_address",
        "mother_name",
        "mother_address",
        "emergency_contact",
        "nationality",
        "origin_county",
        "marital_status",
        "gender",
    )

    class Meta:
        model = Student
        fields: FieldT = []

    def __init__(self, *args, **kwargs) -> None:
        """Set initial curriculum value from primary enrollment."""
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["primary_curriculum"].initial = self.instance.primary_curriculum

    def save(self, commit=True):
        """Persist student and map selected curriculum to primary enrollment."""
        student = super().save(commit=commit)
        curriculum = self.cleaned_data.get("primary_curriculum")
        if curriculum is not None:
            set_primary_std_curri_enroll(
                student,
                curriculum,
                entry_semester_id=student.entry_semester_id,
                is_active=True,
            )
        return student
