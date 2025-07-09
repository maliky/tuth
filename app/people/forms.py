"""Defines model forms for the people module."""

import pdb
from typing import Any
from django.contrib.auth.models import User
from app.people.models.student import Student
from django import forms


class StudentFrom(forms.ModelForm):

    first_name = forms.CharField(label="first_name", required=True)
    last_name = forms.CharField(label="last_name", required=True)
    username = forms.CharField(label="username", required=False, disabled=True)
    email = forms.EmailField(label="email", required=False, disabled=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            user = self.instance.user
            for u_attr in ["first_name", "last_name", "username", "email"]:
                self.fields[u_attr].initial = getattr(user, u_attr, "")

            self.fields["username"].widget.attrs["readonly"] = True
            self.fields["email"].widget.attrs["readonly"] = True

    def clean(self):
        """Check the data entered in the form and update the user accordingly."""

        cleaned_data = super().clean()
        d = {
            "first_name": cleaned_data["first_name"],
            "last_name": cleaned_data["last_name"],
            "middle_name": cleaned_data.get("middle_name", ""),
        }

        if {"first_name", "middle_name", "last_name"} & set(self.changed_data):
            student = self.instance
            d["username"] = student.mk_username(
                first=d["first_name"], last=d["last_name"], middle=d["middle_name"]
            )
            d["email"] = student.mk_email(d["username"])
            if student.user_id:
                for u_field, d_value in d.items():
                    setattr(student.user, u_field, d_value)
                student.user.save()

            cleaned_data["username"] = d["username"]
            cleaned_data["email"] = d["email"]

        return cleaned_data

    def save(self, commit=True):
        """Save the data on in DB creating the user on the fly."""
        student = super().save(commit=False)  # save student only fields first

        first = self.cleaned_data.get("first_name", "")
        last = self.cleaned_data.get("last_name", "")
        username = self.cleaned_data.get("username", "")
        email = self.cleaned_data.get("email", "")
        _user, user_created = User.objects.get_or_create(
            username=username,
            defaults={"first_name": first, "last_name": last, "email": email},
        )
        student.user = _user
        
        if not user_created:   # we update
            _user.first_name = first
            _user.last_name = last
            _user.email = email
            
            _user.save(update_fields=["first_name", "last_name", "email"])

        student._update_long_name()
        student.save()

        return student

    class Meta:
        model = Student
        fields = [
            "name_prefix",
            "first_name",
            "middle_name",
            "last_name",
            "first_name",
            "name_suffix",
            "date_of_birth",
            "phone_number",
            "physical_address",
            "bio",
            "photo",
            "username",
            "email",
        ]
