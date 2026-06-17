"""Template context processors for portal-wide UI identity."""

from __future__ import annotations

from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest

from app.website.services.account_profile import PortalIdentityT, build_portal_identity


def portal_identity(request: HttpRequest) -> dict[str, PortalIdentityT | None]:
    """Expose the current user's portal identity to all templates."""
    user = request.user
    if isinstance(user, AnonymousUser) or not user.is_authenticated:
        return {"portal_identity": None}
    return {"portal_identity": build_portal_identity(user)}


__all__ = ["portal_identity"]
