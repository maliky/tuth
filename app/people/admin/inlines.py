"""Inlines forms for the admin interface of people."""
from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm


class UserInline(admin.StackedInline):
    model = User
    form = UserCreationForm
    can_delete = False
    verbose_name_plural = "User"
    fields = ("username", "first_name", "last_name", "email", "password1", "password2")
