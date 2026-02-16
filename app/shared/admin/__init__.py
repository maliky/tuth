"""Initialisation of the init module of the shared admin module."""

from typing import Any

from django.contrib import admin
from django.contrib.admin.sites import AdminSite

from app.shared.admin.mixins import CollegeRestrictedAdmin, DptRestrictedAdmin

# register customized Group admin
from app.shared.admin.group import GpAdmin

__all__ = [
    "CollegeRestrictedAdmin",
    "DptRestrictedAdmin",
    "GpAdmin",
]


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


def _gp_admin_models(app_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def _gped_get_app_list(
    site: AdminSite,
    request,
    app_label: str | None = None,
) -> list[dict[str, Any]]:
    """Hook AdminSite.get_app_list to group lookup models together."""
    app_list = AdminSite.get_app_list(site, request, app_label=app_label)
    if app_label:
        return app_list
    return _gp_admin_models(app_list)


admin.site.get_app_list = _gped_get_app_list.__get__(  # type: ignore[method-assign]
    admin.site, AdminSite
)
