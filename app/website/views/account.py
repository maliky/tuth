"""Account self-service profile views."""

from __future__ import annotations

from typing import TypedDict, cast

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from app.people.models.student import Student
from app.website.forms.account import AccountProfileForm
from app.website.services.account_profile import (
    build_portal_identity,
    profile_facts,
    profile_for_user,
)
from app.website.services.staff_portal import (
    build_staff_role_switcher,
    build_staff_sidebar_links,
    resolve_staff_role,
)
from app.website.views.student_helpers import _build_sidebar_links

PROFILE_EDIT_MODE = "edit"


class ProfileDisplayItemT(TypedDict):
    """A single read-only profile row with explicit empty-state metadata."""

    label: str
    value: str
    is_missing: bool


class ProfileDisplaySectionT(TypedDict):
    """A grouped read-only section for the account profile page."""

    title: str
    items: list[ProfileDisplayItemT]


def _profile_sidebar_context(user: User) -> dict[str, object]:
    """Return sidebar navigation appropriate for the user's active portal."""
    profile = profile_for_user(user)
    if isinstance(profile, Student):
        return {
            "sidebar_links": _build_sidebar_links("Profile", student=profile),
            "role_switcher": [],
            "sidebar_nav_label": "Student services",
            "sidebar_footer_title": "Advising",
            "sidebar_footer_text": "advising@tusis.edu",
        }

    role_slug = resolve_staff_role(user)
    return {
        "sidebar_links": build_staff_sidebar_links(role_slug, active_key="profile"),
        "role_switcher": build_staff_role_switcher(user, role_slug),
        "sidebar_nav_label": "Tasks",
        "sidebar_footer_title": "Support",
        "sidebar_footer_text": "admin@tubmanu.edu.lr",
    }


def _profile_breadcrumbs(user: User) -> list[dict[str, str]]:
    """Return breadcrumbs back to the user's natural dashboard."""
    profile = profile_for_user(user)
    if isinstance(profile, Student):
        dashboard_url = reverse("student_dashboard")
        dashboard_label = "Student Dashboard"
    else:
        dashboard_url = reverse("staff_dashboard")
        dashboard_label = "Staff Dashboard"
    return [
        {"label": dashboard_label, "href": dashboard_url},
        {"label": "My profile", "href": ""},
    ]


def _field_value(form: AccountProfileForm, field_name: str) -> str:
    """Return a display value for one account profile form field."""
    value = form[field_name].value()
    if value in {None, ""}:
        return "Not set"
    if field_name == "gender":
        return {"f": "Female", "m": "Male"}.get(str(value), str(value))
    return str(value)


def _is_missing_field_value(form: AccountProfileForm, field_name: str) -> bool:
    """Return whether a read-only profile field has no user supplied value."""
    return form[field_name].value() in {None, ""}


def _section_items(
    form: AccountProfileForm,
    field_names: tuple[str, ...],
) -> list[ProfileDisplayItemT]:
    """Return display rows for the requested form fields."""
    return [
        {
            "label": str(form.fields[field_name].label),
            "value": _field_value(form, field_name),
            "is_missing": _is_missing_field_value(form, field_name),
        }
        for field_name in field_names
    ]


def _profile_display_sections(form: AccountProfileForm) -> list[ProfileDisplaySectionT]:
    """Return grouped read-only personal details from the profile form."""
    return [
        {
            "title": "Name",
            "items": _section_items(
                form,
                (
                    "prefix_name",
                    "first_name",
                    "middle_name",
                    "last_name",
                    "suffix_name",
                ),
            ),
        },
        {
            "title": "Contact",
            "items": _section_items(
                form,
                ("email", "phone_number", "physical_address"),
            ),
        },
        {
            "title": "Personal details",
            "items": _section_items(
                form,
                (
                    "birth_date",
                    "birth_place",
                    "gender",
                    "nationality",
                    "origin_county",
                    "marital_status",
                ),
            ),
        },
    ]


def _is_edit_mode(request: HttpRequest) -> bool:
    """Return whether the profile page should render editable fields."""
    return request.method == "POST" or request.GET.get("mode") == PROFILE_EDIT_MODE


@login_required
def account_profile(request: HttpRequest) -> HttpResponse:
    """Render and process the current user's self-service profile."""
    user = cast(User, request.user)
    profile = profile_for_user(user)
    form = AccountProfileForm(
        request.POST or None,
        request.FILES or None,
        user=user,
        profile=profile,
    )
    if request.method == "POST" and form.is_valid():
        profile = form.save()
        messages.success(request, "Profile updated.")
        return redirect("account_profile")

    profile_url = reverse("account_profile")
    context: dict[str, object] = {
        "form": form,
        "page_title": "My profile",
        "page_summary": "Review your profile and update safe personal contact details.",
        "eyebrow": "Account",
        "is_edit_mode": _is_edit_mode(request),
        "edit_profile_url": f"{profile_url}?mode={PROFILE_EDIT_MODE}",
        "profile_url": profile_url,
        "portal_identity": build_portal_identity(user),
        "profile_display_sections": _profile_display_sections(form),
        "profile_facts": profile_facts(user, profile),
        "breadcrumbs": _profile_breadcrumbs(user),
        "sidebar_identity_url": profile_url,
    }
    context.update(_profile_sidebar_context(user))
    return render(request, "website/account_profile.html", context)


__all__ = ["account_profile"]
