"""Compatibility façade for staff portal services."""

from __future__ import annotations

from app.website.services.portal_types import (
    ActionT,
    BreadcrumbT,
    DashboardLinkT,
    DisplayValueT,
    MetricT,
    PanelItemT,
    PanelT,
    RoleConfig,
    RoleContextT,
    RoleSwitcherLinkT,
    RoleTaskT,
    SidebarLinkT,
)
from app.website.services.staff_common import ADMIN_PORTAL_GROUPS
from app.website.services.staff_dashboard_service import render_role_dashboard
from app.website.services.staff_roles import (
    ROLE_CONFIG,
    ROLE_TASKS,
    build_staff_role_switcher,
    build_staff_sidebar_links,
    resolve_staff_role,
    user_can_access_role,
)

__all__ = [
    "ADMIN_PORTAL_GROUPS",
    "ActionT",
    "BreadcrumbT",
    "DashboardLinkT",
    "DisplayValueT",
    "MetricT",
    "PanelItemT",
    "PanelT",
    "ROLE_CONFIG",
    "ROLE_TASKS",
    "RoleConfig",
    "RoleContextT",
    "RoleSwitcherLinkT",
    "RoleTaskT",
    "SidebarLinkT",
    "build_staff_role_switcher",
    "build_staff_sidebar_links",
    "render_role_dashboard",
    "resolve_staff_role",
    "user_can_access_role",
]
