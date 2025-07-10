"""The base form to manipulate users in Admin."""

from __future__ import annotations
import pdb
from typing import Any, Dict, TypeVar
from django import forms
from django.contrib.auth import get_user_model
from django.db import transaction
from django.contrib.auth.models import User

PersonT = TypeVar("PersonT")  # ? what is this.


class PersonFormMixin(forms.ModelForm):
    """Provide the form for editing a abstract user and the attached user.

    Add four fields to update or create the user on the fly.
    Set constantes to be display on the admin interface.
    """

    USER_FIELDS = ["first_name", "last_name", "username", "email"]
    STANDARD_USER_FIELDS = [
        "middle_name",
        "name_prefix",
        "name_suffix",
        "phone_number",
        "physical_address",
    ]

    first_name = forms.CharField(label="first_name", required=True)
    last_name = forms.CharField(label="last_name", required=True)
    username = forms.CharField(label="username", required=False, disabled=True)
    email = forms.EmailField(label="email", required=False, disabled=True)

    def __init_subclass__(cls, **kwargs) -> None:
        """Set the field attribute of the Meta class of the subclass.

        Theses are the field to be displayed on the form.
        """
        super().__init_subclass__(**kwargs)
        specific = getattr(cls, "SPECIFIC_FIELDS", [])
        cls.Meta.fields = cls.STANDARD_USER_FIELDS + cls.USER_FIELDS + specific

    def __init__(self, *args, **kwargs):
        """Initialize the form."""
        super().__init__(*args, **kwargs)

        for f, v in self._get_initial_user_values().items():
            self.fields[f].initial = v

        self.fields["username"].widget.attrs["readonly"] = True
        self.fields["email"].widget.attrs["readonly"] = True

    def _get_initial_user_values(self) -> Dict[str, str]:
        """Returns the existing attribute for the user."""
        # the instance all have a user or should.
        if self.instance and self.instance.pk:
            return {f: getattr(self.instance.user, f, "") for f in self.USER_FIELDS}
        return {f: "" for f in self.USER_FIELDS}

    def clean(self) -> dict[str, Any]:
        """Check the data entered in the form and update the user accordingly."""

        cd = super().clean()  # -> cleaned_data
        person = self.instance

        # we check if a field used to create the underlining user has changed.
        if {"first_name", "middle_name", "last_name"} & set(self.changed_data):
            cd["username"] = person.mk_username(
                first=cd["first_name"],
                last=cd["last_name"],
                middle=cd["middle_name"],
            )
            cd["email"] = person.mk_email(cd["username"])

            # we update the user early.
            # if person.user_id:
            #     for f in self.USER_FIELDS:
            #         setattr(person.user, f, cd[f])
            #     person.user.save()

        return cd

    @transaction.atomic
    def save(self, commit=True) -> PersonT:
        """Save the data on in DB creating the user on the fly."""
        person: PersonT = super().save(commit=False)  # save person only fields first
        cd = self.cleaned_data

        _user, user_created = User.objects.update_or_create(
            pk=getattr(person, "user_id", None),
            defaults={
                "username": cd.get("username"),
                "first_name": cd.get("first_name", ""),
                "last_name": cd.get("last_name", ""),
                "email": cd.get("email", ""),
            },
        )
        person.user = _user
        person._update_long_name()
        person.save()

        return person
