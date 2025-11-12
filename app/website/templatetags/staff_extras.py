"""Template helpers for staff dashboards and admin integration."""

from __future__ import annotations

from typing import Any

from django import template
from django.urls import reverse

from app.website.views.staff_dashboards import ROLE_CONFIG, _resolve_staff_role

register = template.Library()


@register.simple_tag(takes_context=True)
def staff_dashboard_info(context: dict[str, Any]) -> dict[str, str]:
    """Return the current user's role slug/title/url for use in templates."""
    request = context.get("request")
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {}
    try:
        role_slug = _resolve_staff_role(user)
    except Exception:  # pragma: no cover - safety net
        return {}
    if not role_slug:
        return {}
    config = ROLE_CONFIG.get(role_slug)
    if not config:
        return {}
    return {
        "slug": role_slug,
        "title": config["title"],
        "url": reverse("staff_role_dashboard", args=[role_slug]),
    }
