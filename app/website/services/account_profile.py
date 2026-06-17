"""Shared helpers for portal account identity and self-service profiles."""

from __future__ import annotations

from typing import Literal, TypeAlias, TypedDict, cast

from django.contrib.auth.models import User

from app.people.models.donor import Donor
from app.people.models.faculty import Faculty
from app.people.models.staffs import Staff
from app.people.models.student import Student

PersonProfileT: TypeAlias = Staff | Student | Donor
ProfileKindT: TypeAlias = Literal["Faculty", "Staff", "Student", "Donor", "Account"]


class PortalIdentityT(TypedDict):
    """Display identity used by portal sidebars and profile pages."""

    name: str
    subtitle: str
    initial: str
    avatar_url: str
    kind: ProfileKindT


class ProfileFactT(TypedDict):
    """Read-only profile fact displayed beside the self-service form."""

    label: str
    value: str


def profile_for_user(user: User) -> PersonProfileT | None:
    """Return the first person profile attached to the user account."""
    for attr in ("staff", "student", "donor"):
        try:
            return cast(PersonProfileT, getattr(user, attr))
        except (
            AttributeError,
            Staff.DoesNotExist,
            Student.DoesNotExist,
            Donor.DoesNotExist,
        ):
            continue
    return None


def _has_faculty_profile(profile: Staff) -> bool:
    """Return whether a saved staff profile has a linked faculty record."""
    profile_id = cast(int | None, getattr(profile, "pk", None))
    if profile_id is None:
        return False
    return Faculty.objects.filter(staff_profile_id=profile_id).exists()


def profile_kind(profile: PersonProfileT | None) -> ProfileKindT:
    """Return the user-facing profile type."""
    if isinstance(profile, Staff):
        if _has_faculty_profile(profile):
            return "Faculty"
        return "Staff"
    if isinstance(profile, Student):
        return "Student"
    if isinstance(profile, Donor):
        return "Donor"
    return "Account"


def profile_display_name(user: User, profile: PersonProfileT | None) -> str:
    """Return the best human-readable name for a portal identity."""
    if profile and profile.long_name:
        return profile.long_name
    return user.get_full_name() or user.username


def profile_identifier(user: User, profile: PersonProfileT | None) -> str:
    """Return a stable identifier shown below the display name."""
    if profile is not None and profile.obj_id:
        return profile.obj_id
    return user.username


def profile_avatar_url(profile: PersonProfileT | None) -> str:
    """Return the profile photo URL when a file is available."""
    if profile is None or not getattr(profile, "photo", None):
        return ""
    try:
        return str(profile.photo.url)
    except ValueError:
        return ""


def build_portal_identity(user: User) -> PortalIdentityT:
    """Build the sidebar identity for the authenticated portal user."""
    profile = profile_for_user(user)
    name = profile_display_name(user, profile)
    subtitle = profile_identifier(user, profile)
    initial = (name or user.username or "TU")[:1]
    return {
        "name": name,
        "subtitle": subtitle,
        "initial": initial,
        "avatar_url": profile_avatar_url(profile),
        "kind": profile_kind(profile),
    }


def profile_facts(user: User, profile: PersonProfileT | None) -> list[ProfileFactT]:
    """Return read-only account facts that should not be self-edited."""
    facts: list[ProfileFactT] = [
        {"label": "Username", "value": user.username},
        {"label": "Profile type", "value": profile_kind(profile)},
    ]
    if isinstance(profile, Staff):
        facts.extend(
            [
                {"label": "Staff ID", "value": profile.staff_id or "Pending"},
                {"label": "Position", "value": profile.position or "Not set"},
                {"label": "Department", "value": str(profile.department or "Unassigned")},
                {"label": "Division", "value": profile.division or "Not set"},
            ]
        )
    elif isinstance(profile, Student):
        facts.extend(
            [
                {"label": "Student ID", "value": profile.student_id or "Pending"},
                {"label": "Program", "value": str(profile.primary_curriculum)},
            ]
        )
    elif isinstance(profile, Donor):
        facts.append({"label": "Donor ID", "value": profile.donor_id or "Pending"})
    return facts


__all__ = [
    "PersonProfileT",
    "PortalIdentityT",
    "ProfileFactT",
    "ProfileKindT",
    "build_portal_identity",
    "profile_avatar_url",
    "profile_display_name",
    "profile_facts",
    "profile_for_user",
    "profile_identifier",
    "profile_kind",
]
