"""The form to manipulate faculty in the Admin."""

from __future__ import annotations, division
from typing import Any, Dict

from app.academics.models.department import Department
from app.people.models.staffs import Staff
from app.shared.types import FieldT
from django import forms
from django.db import transaction
from django.contrib.auth.models import User


class FacultyForm(forms.ModelForm):
    """Provide the form for editing a faculty user and the attached staff & user."""

    first_name = forms.CharField(label="first_name", required=True)
    last_name = forms.CharField(label="last_name", required=True)

    username = forms.CharField(label="username", required=False, disabled=True)
    email = forms.EmailField(label="email", required=False, disabled=True)
    staff_id = forms.CharField(label="staff_id", required=False, disabled=True)

    employment_date = forms.DateField(label="date", required=False)
    division = forms.CharField(label="division", required=False)
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        widget=forms.Select,
        required=False,
        label="Teaching department",
        help_text="Leave blank if not assigned yet",
    )
    position = forms.CharField(label="position", required=False)

    FACULTY_FIELDS = ("academic_rank", "college", "google_profile", "personal_website")
    USER_FIELDS = ("first_name", "last_name", "username", "email")
    STAFF_FIELDS = ("staff_id", "employment_date", "division", "department", "position")

    def _get_initial_field_values(self) -> Dict[str, str]:
        """Returns the existing attribute for the user and staff used to initialise the form."""
        fields = list(self.USER_FIELDS) + list(self.STAFF_FIELDS)
        if self.instance and self.instance.pk:
            _staff = self.instance.staff_profile
            _user = _staff.user
            return {f: getattr(_user, f, "") for f in fields}

        return {f: "" for f in fields}

    def __init__(self, *args, **kwargs) -> None:
        """We set initial values to all fields."""
        super().__init__(*args, **kwargs)

        self.initial.update(self._get_initial_field_values().items())

        self.fields["username"].widget.attrs["readonly"] = True
        self.fields["email"].widget.attrs["readonly"] = True
        self.fields["staff_id"].widget.attrs["readonly"] = True

    def clean(self) -> dict[str, Any]:
        """Check the data entered in the form and update the user accordingly."""

        cd = super().clean()  # -> cleaned_data
        if not cd:
            return {"": None}

        faculty = self.instance

        # we check if a field used to create the underlining user has changed.
        if {"first_name", "middle_name", "last_name"} & set(self.changed_data):
            cd["username"] = faculty.staff_profile.mk_username(
                first=cd.get("first_name", ""),
                last=cd.get("last_name", ""),
                middle=cd.get("middle_name", ""),
            )
            cd["email"] = faculty.staff_profile.mk_email(cd.get("username", ""))

        return cd

    @transaction.atomic
    def save(self, commit=True):
        """Save the data on in DB creating the user on the fly."""
        cd = self.cleaned_data

        faculty = super().save(commit=False)  # save person only fields first

        if faculty.pk:
            _staff = faculty.staff_profile
            _user_id = _staff.user_id
        else:
            _user_id = None

        _user, _ = User.objects.update_or_create(
            pk=_user_id, defaults={f: cd.get(f, None) for f in self.USER_FIELDS}
        )
        staff, _ = Staff.objects.update_or_create(
            pk=_staff.pk, defaults={f: cd.get(f, None) for f in self.STAFF_FIELDS}
        )

        staff.user = _user
        staff._update_long_name()
        faculty.staff_profile = staff
        faculty.save()

        return faculty

    class Meta:
        # just a place holder for override
        fields: FieldT = []
