"""Defines model forms for the people module."""

import pdb
from typing import Any
from app.people.forms.base import PersonFormMixin
from app.people.models.donor import Donor
from app.people.models.staffs import Staff
from django.contrib.auth.models import User
from app.people.models.student import Student
from django import forms


class DonorForm(PersonFormMixin, forms.ModelForm):

    class Meta:
        model = Donor
        fields = []


# class FacultyFrom(forms.ModelForm):
#     """Need a form to create a staff on the fly."""

#     None


class StaffForm(PersonFormMixin, forms.ModelForm):
    SPECIFIC_FIELDS = ["division", "department", "position", "employment_date"]

    class Meta:
        model = Staff
        fields = []


class StudentForm(PersonFormMixin, forms.ModelForm):
    SPECIFIC_FIELDS = ["date_of_birth", "bio", "photo"]

    class Meta:
        model = Student
        fields = []
