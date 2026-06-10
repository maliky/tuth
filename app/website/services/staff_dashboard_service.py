"""Rendering service for staff portal dashboards."""

from __future__ import annotations

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse

from app.website.services.portal_types import BreadcrumbT, PortalContextT
from app.website.services.staff_common import _annotate_admin_actions, _as_user
from app.website.services.staff_roles import (
    ROLE_CONFIG,
    _build_accessible_dashboard_links,
    build_staff_role_switcher,
    build_staff_sidebar_links,
)


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
    # Keep admin escape hatches out of the portal action panel.
    base["actions"] = _annotate_admin_actions(context["actions"])
    base["accessible_dashboards"] = accessible_links
    base["role_switcher"] = role_switcher
    template_name = config.get("template", "website/staff/role_dashboard.html")
    sidebar_links = build_staff_sidebar_links(role_slug)
    breadcrumbs: list[BreadcrumbT] = [
        {"label": "Staff Workspace", "href": reverse("staff_dashboard")},
        {"label": config["title"], "href": ""},
    ]

    base.update({"sidebar_links": sidebar_links, "breadcrumbs": breadcrumbs})
    return render(request, template_name, base)


__all__ = ["render_role_dashboard"]
