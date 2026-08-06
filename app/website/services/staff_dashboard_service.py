"""Rendering service for staff portal dashboards."""

from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import urlsplit, urlunsplit

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse

from app.academics.career_scope import (
    CAREER_QUERY_PARAM,
    academic_career_theme_class,
    career_selector_context,
    normalize_academic_career,
)
from app.website.services.portal_types import (
    ActionT,
    BreadcrumbT,
    PortalContextT,
    SidebarLinkT,
)
from app.website.services.staff_common import _annotate_admin_actions, _as_user
from app.website.services.staff_student_search import dashboard_student_search_context
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


def _selected_career_from_context(context: Mapping[str, object]) -> object:
    """Return selected career from the role context, if present."""
    direct = context.get("selected_academic_career")
    if direct:
        return direct
    career_selector = context.get("career_selector")
    if isinstance(career_selector, dict):
        selected = career_selector.get("selected")
        if selected:
            return selected
    academic_dashboard = context.get("academic_dashboard")
    if isinstance(academic_dashboard, dict):
        selected = academic_dashboard.get("selected_academic_career")
        if selected:
            return selected
    return ""


def _selected_career_param(
    request: HttpRequest,
    context: Mapping[str, object],
) -> str | None:
    """Return the career scope that should be preserved in navigation links."""
    selected = _selected_career_from_context(context)
    if selected:
        return str(selected)
    return request.GET.get(CAREER_QUERY_PARAM) or None


def render_role_dashboard(request: HttpRequest, role_slug: str) -> HttpResponse:
    """Render one staff role dashboard using the shared portal shell."""
    config = ROLE_CONFIG.get(role_slug)
    if not config:
        raise Http404("Unknown staff dashboard.")
    context = config["builder"](request)
    selected_career_param = _selected_career_param(request, context)
    selected_career = normalize_academic_career(selected_career_param)
    accessible_links = _build_accessible_dashboard_links(
        _as_user(request.user),
        role_slug,
        academic_career=selected_career_param,
    )
    role_switcher = build_staff_role_switcher(
        _as_user(request.user),
        role_slug,
        academic_career=selected_career_param,
    )
    base: PortalContextT = {
        "title": config["title"],
        "summary": config["summary"],
        "role_slug": role_slug,
        "page_title": config["title"],
        "page_summary": config["summary"],
        "eyebrow": role_slug.replace("_", " ").title(),
    }
    base.update(context)
    if "portal_theme_class" not in base:
        base["portal_theme_class"] = academic_career_theme_class(
            _selected_career_from_context(context)
        )
    if "career_selector" not in base:
        base["career_selector"] = career_selector_context(
            request.GET,
            action_url=reverse("staff_role_dashboard", args=[role_slug]),
        )
    base["dashboard_student_search"] = dashboard_student_search_context(
        role_slug,
        selected_career,
    )
    sidebar_links = build_staff_sidebar_links(
        role_slug,
        academic_career=selected_career_param,
    )
    # Keep admin escape hatches out of the portal action panel.
    actions = _dedupe_sidebar_actions(
        _annotate_admin_actions(context["actions"]),
        sidebar_links,
    )
    base["actions"] = actions
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
