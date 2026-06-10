"""Shared typed shapes for Tusis portal contexts and components."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import NotRequired, TypeAlias, TypedDict

from django.http import HttpRequest

DisplayValueT: TypeAlias = str | int | float | bool | None
PortalContextT: TypeAlias = dict[str, object]
RoleSlugT: TypeAlias = str
RoleEdgeT: TypeAlias = tuple[RoleSlugT, RoleSlugT]


class MetricT(TypedDict):
    """A compact dashboard metric displayed in a portal KPI card."""

    label: str
    value: DisplayValueT


class PanelItemT(TypedDict):
    """One row inside a portal panel card."""

    label: str
    value: DisplayValueT
    meta: NotRequired[str]


class PanelT(TypedDict):
    """A portal panel card and its display rows."""

    title: str
    items: list[PanelItemT]
    subtitle: NotRequired[str]


class ActionT(TypedDict):
    """A call-to-action rendered in the shared portal action panel."""

    label: str
    href: str
    description: str
    variant: str
    is_admin: NotRequired[bool]


class RoleContextT(TypedDict):
    """Dashboard payload returned by a staff role context builder."""

    metrics: list[MetricT]
    panels: list[PanelT]
    actions: list[ActionT]


class DashboardLinkT(TypedDict):
    """A staff workspace available to the current user."""

    label: str
    summary: str
    href: str
    active: bool
    slug: str


class RoleSwitcherLinkT(TypedDict):
    """A sidebar role switcher option."""

    label: str
    href: str
    active: bool


class SidebarLinkT(TypedDict):
    """A task-oriented sidebar navigation link."""

    label: str
    href: str
    active: bool
    icon: str


class RoleTaskT(TypedDict):
    """Configuration for one role-specific sidebar task."""

    label: str
    route_name: str
    icon: str
    args: NotRequired[list[str]]
    key: NotRequired[str]
    query: NotRequired[str]


class BreadcrumbT(TypedDict):
    """A shared breadcrumb entry for portal pages."""

    label: str
    href: str


class RoleConfig(TypedDict, total=False):
    """Configuration for one staff role workspace."""

    groups: set[str]
    title: str
    summary: str
    builder: Callable[[HttpRequest], RoleContextT]
    template: str


RoleConfigMapT: TypeAlias = Mapping[RoleSlugT, RoleConfig]
RoleParentMapT: TypeAlias = dict[RoleSlugT, frozenset[RoleSlugT]]
RoleChildMapT: TypeAlias = dict[RoleSlugT, frozenset[RoleSlugT]]

__all__ = [
    "ActionT",
    "BreadcrumbT",
    "DashboardLinkT",
    "DisplayValueT",
    "MetricT",
    "PanelItemT",
    "PanelT",
    "PortalContextT",
    "RoleChildMapT",
    "RoleConfig",
    "RoleConfigMapT",
    "RoleContextT",
    "RoleEdgeT",
    "RoleParentMapT",
    "RoleSlugT",
    "RoleSwitcherLinkT",
    "RoleTaskT",
    "SidebarLinkT",
]
