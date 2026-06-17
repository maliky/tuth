"""Self-service account profile forms."""

from __future__ import annotations

from datetime import date
from typing import TypedDict, cast

from django import forms
from django.contrib.auth.models import User
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction

from app.website.services.account_profile import PersonProfileT


class AccountProfileDataT(TypedDict):
    """Cleaned values accepted by the self-service profile form."""

    prefix_name: str
    first_name: str
    middle_name: str
    last_name: str
    suffix_name: str
    email: str
    phone_number: str
    physical_address: str
    birth_date: date | None
    birth_place: str
    gender: str
    nationality: str
    origin_county: str
    marital_status: str
    photo: UploadedFile | None


PERSON_PROFILE_FIELDS: tuple[str, ...] = (
    "prefix_name",
    "middle_name",
    "suffix_name",
    "phone_number",
    "physical_address",
    "birth_date",
    "birth_place",
    "gender",
    "nationality",
    "origin_county",
    "marital_status",
)


def _long_name(data: AccountProfileDataT) -> str:
    """Return the canonical display name from submitted name parts."""
    parts = (
        data["prefix_name"],
        data["first_name"],
        data["middle_name"],
        data["last_name"],
        data["suffix_name"],
    )
    return " ".join(part for part in parts if part).strip()


class AccountProfileForm(forms.Form):
    """Allow users to update safe personal/contact fields on their own profile."""

    prefix_name = forms.CharField(
        label="Prefix",
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    first_name = forms.CharField(
        label="First name",
        required=False,
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
        required=False,
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    suffix_name = forms.CharField(
        label="Suffix",
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    email = forms.EmailField(
        label="Email",
        required=False,
        widget=forms.EmailInput(attrs={"class": "form-control"}),
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
    photo = forms.ImageField(
        label="Profile photo",
        required=False,
        widget=forms.FileInput(attrs={"class": "form-control", "accept": "image/*"}),
    )

    def __init__(self, *args, user: User, profile: PersonProfileT | None, **kwargs):
        """Populate the form from the current auth user and person profile."""
        super().__init__(*args, **kwargs)
        self.user = user
        self.profile = profile
        self._set_initial_values()

    def _set_initial_values(self) -> None:
        """Load current account values into form initial data."""
        self.fields["first_name"].initial = self.user.first_name
        self.fields["last_name"].initial = self.user.last_name
        self.fields["email"].initial = self.user.email
        if self.profile is None:
            return
        for field_name in PERSON_PROFILE_FIELDS:
            self.fields[field_name].initial = getattr(self.profile, field_name)

    def _cleaned_profile_data(self) -> AccountProfileDataT:
        """Return cleaned_data narrowed to the form's typed payload."""
        return cast(AccountProfileDataT, self.cleaned_data)

    def _profile_field_values(self) -> dict[str, object]:
        """Return person-profile field values keyed by model field name."""
        return {
            field_name: self.cleaned_data.get(field_name)
            for field_name in PERSON_PROFILE_FIELDS
        }

    @transaction.atomic
    def save(self) -> PersonProfileT | None:
        """Persist the submitted account and profile values."""
        data = self._cleaned_profile_data()
        self.user.first_name = data["first_name"]
        self.user.last_name = data["last_name"]
        self.user.email = data["email"]
        self.user.save(update_fields=["first_name", "last_name", "email"])
        if self.profile is None:
            return None

        for field_name, value in self._profile_field_values().items():
            setattr(self.profile, field_name, value)
        self.profile.long_name = _long_name(data)
        self.profile.email = data["email"]
        self.profile.username = self.user.username
        update_fields = [
            *PERSON_PROFILE_FIELDS,
            "long_name",
            "email",
            "username",
        ]
        photo = data.get("photo")
        if photo:
            self.profile.photo = photo
            update_fields.append("photo")
        self.profile.save(update_fields=update_fields)
        return self.profile


__all__ = ["AccountProfileDataT", "AccountProfileForm"]
