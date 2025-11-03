"""Defines model forms for the people module."""

from app.people.forms.base import PersonFormMixin
from app.people.models.donor import Donor
from app.people.models.staffs import Staff
from app.people.models.student import Student
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


class StudentForm(PersonFormMixin, forms.ModelForm):
    SPECIFIC_FIELDS = (
        "student_id",
        "curriculum",
        "current_enrolled_semester",
        "entry_semester",
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
