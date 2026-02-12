"""Add the ability to handle user from the groupadmin view."""

from typing import Any

from django import forms
from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.auth.admin import GroupAdmin as BaseGpAdmin
from django.contrib.auth.models import Group, User


class GpAdminForm(forms.ModelForm):
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


class GpAdmin(BaseGpAdmin):
    form = GpAdminForm
    filter_horizontal = ("users",)


admin.site.unregister(Group)
admin.site.register(Group, GpAdmin)

ADMIN_GROUP_MODEL_LABELS = {
    "academics.CurriStatus",
    "finance.AccountType",
    "finance.AccountChartType",
    "finance.FeeType",
    "finance.InvoiceStatus",
    "finance.PaymentMethod",
    "finance.PaymentStatus",
    "finance.Payer",
    "finance.CourseInvoice",
    "finance.CourseFeeStack",
    "finance.FeeStack",
    "finance.FeeStackLine",
    "registry.CreditHour",
    "registry.DocStatus",
    "registry.DocType",
    "registry.GradeValue",
    "registry.RegistrationStatus",
    "registry.TranscriptRequestStatus",
    "timetable.SemesterStatus",
}


def _group_admin_models(app_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return app list with lookup and utility models under the Admin heading."""
    admin_models: list[dict[str, Any]] = []
    grouped_apps: list[dict[str, Any]] = []
    for app in app_list:
        app_label = app["app_label"]
        is_impersonate = app_label == "impersonate"
        remaining_models: list[dict[str, Any]] = []
        for model in app["models"]:
            model_label = f"{app_label}.{model['object_name']}"
            if is_impersonate or model_label in ADMIN_GROUP_MODEL_LABELS:
                admin_models.append(model)
            else:
                remaining_models.append(model)
        if remaining_models:
            app = {**app, "models": remaining_models}
            grouped_apps.append(app)
    if admin_models:
        grouped_apps.append(
            {
                "name": "Admin",
                "app_label": "admin_group",
                "app_url": "#",
                "has_module_perms": True,
                "models": admin_models,
            }
        )
    return grouped_apps


def _grouped_get_app_list(
    site: AdminSite,
    request,
    app_label: str | None = None,
) -> list[dict[str, Any]]:
    """Hook AdminSite.get_app_list to group lookup models together."""
    app_list = AdminSite.get_app_list(site, request, app_label=app_label)
    if app_label:
        return app_list
    return _group_admin_models(app_list)


# Bind the custom grouping hook to the default admin site.
admin.site.get_app_list = _grouped_get_app_list.__get__(  # type: ignore[method-assign]
    admin.site, AdminSite
)
