"""Add the ability to handle user from the groupadmin view."""

# admin.py
from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.models import Group, User


class GroupAdminForm(forms.ModelForm):
    users = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        required=False,
        widget=FilteredSelectMultiple("Users", False),
    )

    class Meta:
        model = Group
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        """Init."""
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["users"].initial = self.instance.user_set.all()

    def save_m2m(self):
        """Save the update list of users."""
        super().save_m2m()
        self.instance.user_set.set(self.cleaned_data["users"])


class GroupAdmin(BaseGroupAdmin):
    form = GroupAdminForm
    filter_horizontal = ("users",)


admin.site.unregister(Group)
admin.site.register(Group, GroupAdmin)
