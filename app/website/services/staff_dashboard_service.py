"""Rendering service for staff portal dashboards."""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse

from app.website.services.portal_types import (
    ActionT,
    BreadcrumbT,
    PortalContextT,
    SidebarLinkT,
)
from app.website.services.staff_common import _annotate_admin_actions, _as_user
from app.website.services.staff_roles import (
    ROLE_CONFIG,
    _build_accessible_dashboard_links,
    build_staff_role_switcher,
    build_staff_sidebar_links,
)


def _normalized_href(value: str) -> str:
    """Return a comparable URL key for portal sidebar/action targets."""
    href = value.strip()
    if not href or href == "#":
        return ""
    parsed = urlsplit(href)
    path = (parsed.path or href).rstrip("/") or "/"
    query = parsed.query
    if parsed.scheme or parsed.netloc:
        return urlunsplit((parsed.scheme, parsed.netloc, path, "", query))
    return f"{path}?{query}" if query else path


def _sidebar_href_keys(sidebar_links: list[SidebarLinkT]) -> set[str]:
    """Return normalized sidebar targets that should not be repeated as actions."""
    return {
        key for link in sidebar_links for key in [_normalized_href(link["href"])] if key
    }


def _dedupe_sidebar_actions(
    actions: list[ActionT],
    sidebar_links: list[SidebarLinkT],
) -> list[ActionT]:
    """Drop action cards already represented by the current sidebar."""
    sidebar_targets = _sidebar_href_keys(sidebar_links)
    return [
        action
        for action in actions
        if _normalized_href(str(action.get("href") or "")) not in sidebar_targets
    ]


def render_role_dashboard(request: HttpRequest, role_slug: str) -> HttpResponse:
    """Render one staff role dashboard using the shared portal shell."""
    config = ROLE_CONFIG.get(role_slug)
    if not config:
        raise Http404("Unknown staff dashboard.")
    context = config["builder"](request)
    accessible_links = _build_accessible_dashboard_links(
        _as_user(request.user), role_slug
    )
    role_switcher = build_staff_role_switcher(_as_user(request.user), role_slug)
    base: PortalContextT = {
        "title": config["title"],
        "summary": config["summary"],
        "role_slug": role_slug,
        "page_title": config["title"],
        "page_summary": config["summary"],
        "eyebrow": role_slug.replace("_", " ").title(),
    }
    base.update(context)
    sidebar_links = build_staff_sidebar_links(role_slug)
    # Keep admin escape hatches out of the portal action panel.
    actions = _dedupe_sidebar_actions(
        _annotate_admin_actions(context["actions"]),
        sidebar_links,
    )
    base["actions"] = actions
    base["show_action_panel"] = bool(context.get("show_action_panel", True) and actions)
    base["accessible_dashboards"] = accessible_links
    base["role_switcher"] = role_switcher
    template_name = config.get("template", "website/staff/role_dashboard.html")
    breadcrumbs: list[BreadcrumbT] = [
        {"label": "Staff Dashboard", "href": reverse("staff_dashboard")},
        {"label": config["title"], "href": ""},
    ]

    base.update({"sidebar_links": sidebar_links, "breadcrumbs": breadcrumbs})
    return render(request, template_name, base)


__all__ = ["render_role_dashboard"]
