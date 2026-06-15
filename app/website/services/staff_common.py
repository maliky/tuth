"""Shared helpers for staff portal service modules."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypeAlias, cast

from django.contrib.auth.models import AnonymousUser, User
from django.db.models import Model
from django.urls import NoReverseMatch, reverse

from app.people.models.donor import Donor
from app.people.models.faculty import Faculty
from app.website.services.portal_types import ActionT, AdminShortcutT, RoleContextT

ADMIN_PORTAL_GROUPS = {"System Administrator", "IT Support"}
AdminModelShortcutSpecT: TypeAlias = tuple[str, type[Model]]


def as_user(user: User | AnonymousUser) -> User:
    """Narrow request.user to the concrete User type."""
    return cast(User, user)


def user_gp_names(user: User) -> set[str]:
    """Return the group names attached to a user."""
    return set(user.groups.values_list("name", flat=True))


def get_faculty_profile(user: User) -> Faculty | None:
    """Return the faculty profile linked through staff, if present."""
    staff = getattr(user, "staff", None)
    if not staff:
        return None
    try:
        return cast(Faculty, staff.faculty)
    except Faculty.DoesNotExist:
        return None


def get_donor_profile(user: User) -> Donor | None:
    """Return the donor profile attached to a user, if any."""
    try:
        return user.donor
    except Donor.DoesNotExist:
        return None


def empty_role_context(message: str) -> RoleContextT:
    """Return an informational empty staff role context."""
    return {
        "panels": [
            {
                "title": "Status",
                "items": [
                    {
                        "label": "Info",
                        "value": message,
                    }
                ],
            }
        ],
        "metrics": [],
        "actions": [],
    }


def maybe_reverse(
    name: str,
    args: Sequence[object] | None = None,
    kwargs: dict[str, object] | None = None,
) -> str:
    """Return a URL path, or an empty string when the route is unavailable."""
    try:
        return reverse(name, args=args, kwargs=kwargs)
    except NoReverseMatch:
        return ""


def with_actions(context: RoleContextT, extra: list[ActionT]) -> RoleContextT:
    """Return a role context with additional actions."""
    updated = context.copy()
    updated["actions"] = [*context["actions"], *extra]
    return updated


def admin_shortcuts_for_models(
    user: User,
    specs: Sequence[AdminModelShortcutSpecT],
) -> list[AdminShortcutT]:
    """Return admin changelist shortcuts allowed by the user's view perms."""
    if not user.is_staff:
        return []
    links: list[AdminShortcutT] = []
    for label, model in specs:
        opts = model._meta
        if not user.has_perm(f"{opts.app_label}.view_{opts.model_name}"):
            continue
        try:
            href = reverse(f"admin:{opts.app_label}_{opts.model_name}_changelist")
        except NoReverseMatch:
            continue
        links.append({"label": label, "href": href})
    if not links:
        return []
    return [{"label": "Admin home", "href": reverse("admin:index")}, *links]


def annotate_admin_actions(actions: list[ActionT]) -> list[ActionT]:
    """Return portal-visible actions, hiding Django admin escape hatches."""
    admin_prefix = reverse("admin:index")
    annotated: list[ActionT] = []
    for action in actions:
        href = str(action.get("href") or "")
        is_admin = href.startswith(admin_prefix)
        if is_admin:
            continue
        annotated.append(
            {
                **action,
                "is_admin": is_admin,
                "variant": "warning",
            }
        )
    return annotated


# Compatibility aliases used by extracted legacy context builders.
_as_user = as_user
_user_gp_names = user_gp_names
_get_faculty_profile = get_faculty_profile
_get_donor_profile = get_donor_profile
_empty_role_context = empty_role_context
_maybe_reverse = maybe_reverse
_with_actions = with_actions
_admin_shortcuts_for_models = admin_shortcuts_for_models
_annotate_admin_actions = annotate_admin_actions

__all__ = [
    "ADMIN_PORTAL_GROUPS",
    "AdminModelShortcutSpecT",
    "admin_shortcuts_for_models",
    "annotate_admin_actions",
    "as_user",
    "empty_role_context",
    "get_donor_profile",
    "get_faculty_profile",
    "maybe_reverse",
    "user_gp_names",
    "with_actions",
]
