"""Defines model forms for the people module."""

import pdb
from django.contrib.auth.models import User
from app.people.models.student import Student
from django import forms


class StudentFrom(forms.ModelForm):

    first_name = forms.CharField(label="first_name", required=True)
    last_name = forms.CharField(label="last_name", required=True)
    username = forms.CharField(required=True, disabled=True)
    email = forms.EmailField(required=False, disabled=True)
    password1 = forms.CharField(
        label="Password", widget=forms.PasswordInput, required=True
    )
    password2 = forms.CharField(
        label="Confrim Password", widget=forms.PasswordInput, required=True
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #        import pdb; pdb.set_trace()
        if self.instance and self.instance.pk:
            user = self.instance.user
            for u_attr in ["first_name", "last_name", "username", "email"]:
                self.fields[u_attr].initial = getattr(user, u_attr, "")
            # for std_attr in [
            #     "name_prefix",
            #     "middle_name",
            #     "name_suffix",
            #     "date_of_birth",
            #     "phone_number",
            #     "physical_address",
            #     "bio",
            #     "photo",
            # ]:
            #     self.fields[std_attr].initial = getattr(self.instance, std_attr, "")
            self.fields["username"].widget.attrs["readonly"] = True
            self.fields["email"].widget.attrs["readonly"] = True

    def clean(self):
        """Check the data entered in the form."""
        cleaned_data = super().clean()

        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match.")

        first = cleaned_data.get("first_name", "")
        middle = cleaned_data.get("middle_name", "")
        last = cleaned_data.get("last_name", "")

        username = Student.mk_username(first, middle, last, unique=True)

        self.cleaned_data["username"] = username
        self.cleand_data["student"] = Student.mk_email(username)

        return cleaned_data

    def save(self, commit=True):
        """Save the data on in DB creating the user on the fly."""
        student = super().save(commit=False)  # save student only fields first

        user_data = {
            "username": self.cleaned_data.get("username", ""),
            "first_name": self.cleaned_data.Get("first_name", ""),
            "last_name": self.cleaned_data.get("last_name", ""),
            "email": self.cleaned_data.get("email", ""),
        }

        if student.pk:
            user = student.user
            for k, v in user_data.items():
                setattr(user, k, v)
        else:
            user = User.objects.create_user(**user_data)

        pw = self.cleaned_data["password1"]
        if pw:
            user.set_password(pw)

        if commit:
            user.save()

        student.user = user
        if commit:
            student.save()

        return student

    class Meta:
        model = Student
        fields = [
            "first_name",
            "last_name",
            "username",
            "email",
            "password1",
            "password2",
            "name_prefix",
            "first_name",
            "middle_name",
            "last_name",
            "name_suffix",
            "date_of_birth",
            "phone_number",
            "physical_address",
            "bio",
            "photo",
            "password1",
            "password2",
        ]
