"""Staff portal role configuration and navigation helpers."""

from __future__ import annotations

from collections.abc import Iterable

from django.contrib.auth.models import AnonymousUser, User
from django.urls import reverse

from app.shared.auth.perms import UserRole
from app.website.services.portal_types import (
    DashboardLinkT,
    RoleChildMapT,
    RoleConfig,
    RoleConfigMapT,
    RoleEdgeT,
    RoleParentMapT,
    RoleSlugT,
    RoleSwitcherLinkT,
    RoleTaskT,
    SidebarLinkT,
)
from app.website.services.staff_common import _as_user, _maybe_reverse, _user_gp_names
from app.website.services.staff_contexts import (
    _build_cashier_context,
    _build_chair_context,
    _build_dean_context,
    _build_donor_context,
    _build_enrollment_context,
    _build_enrollment_officer_context,
    _build_faculty_context,
    _build_finance_context,
    _build_finance_officer_context,
    _build_general_context,
    _build_it_context,
    _build_reg_context,
    _build_reg_officer_context,
    _build_scholarship_context,
    _build_staff_context,
    _build_vpaa_context,
)

ROLE_PRIORITY: list[RoleSlugT] = [
    "vpaa",
    "dean",
    "chair",
    "faculty",
    "reg_officer",
    "registrar",
    "enrollment_officer",
    "enrollment",
    "finance_officer",
    "finance",
    "cashier",
    "scholarship",
    "donor",
    "it",
    "staff",
    "general",
]

ROLE_CONFIG: dict[str, RoleConfig] = {
    "staff": {
        "groups": {"Staff"},
        "title": "Staff Workspace",
        "summary": "Common staff entry point and shared shortcuts.",
        "builder": _build_staff_context,
    },
    "faculty": {
        "groups": {"Faculty", "Instructor"},
        "title": "Instruction Hub",
        "summary": "Teaching schedule and grading tasks.",
        "builder": _build_faculty_context,
    },
    "chair": {
        "groups": {"Chair"},
        "title": "Chair Curriculum Center",
        "summary": "Curriculum oversight and workload history.",
        "builder": _build_chair_context,
    },
    "dean": {
        "groups": {"Dean"},
        "title": "Dean Oversight",
        "summary": "Approval queue shared with faculty and students.",
        "builder": _build_dean_context,
    },
    "vpaa": {
        "groups": {"VPAA", "Vice President Academic Affairs"},
        "title": "VPAA Approval Hub",
        "summary": "Centralized decisions for overloads and policies.",
        "builder": _build_vpaa_context,
    },
    "registrar": {
        "groups": {"Registrar"},
        "title": "Registrar Lifecycle Ops",
        "summary": "Transcript fulfillment and live enrollment checks.",
        "builder": _build_reg_context,
    },
    "reg_officer": {
        "groups": {"Registrar Officer"},
        "title": "Registrar Officer Console",
        "summary": "Semester windows and official roster controls.",
        "builder": _build_reg_officer_context,
    },
    "enrollment": {
        "groups": {"Enrollment"},
        "title": "Enrollment Desk",
        "summary": "Student onboarding and document tracking.",
        "builder": _build_enrollment_context,
    },
    "enrollment_officer": {
        "groups": {"Enrollment Officer"},
        "title": "Enrollment Officer Desk",
        "summary": "Supervise onboarding workflows and mass updates.",
        "builder": _build_enrollment_officer_context,
    },
    "finance": {
        "groups": {"Finance"},
        "title": "Finance & Holds",
        "summary": "Invoice tracking and payment validation.",
        "builder": _build_finance_context,
    },
    "cashier": {
        "groups": {"Cashier"},
        "title": "Cashier Station",
        "summary": "Capture walk-in payments and receipt uploads.",
        "builder": _build_cashier_context,
    },
    "finance_officer": {
        "groups": {"Finance Officer"},
        "title": "Finance Officer Control",
        "summary": "Oversee scholarships, invoices, and payment proofs.",
        "builder": _build_finance_officer_context,
    },
    "scholarship": {
        "groups": {"Scholarship Officer"},
        "title": "Scholarship Office",
        "summary": "Donor letters and GPA compliance snapshots.",
        "builder": _build_scholarship_context,
    },
    "donor": {
        "groups": {UserRole.DONOR.value.label},
        "title": "Donor Sponsorship Portal",
        "summary": "Scholarship commitments and beneficiary status.",
        "builder": _build_donor_context,
    },
    "it": {
        "groups": {"IT", "It", "IT Support"},
        "title": "IT Support",
        "summary": "Infrastructure, monitoring, and support queues.",
        "builder": _build_it_context,
    },
    "general": {
        "groups": set(),
        "title": "Staff Workspace",
        "summary": "Common entry point for shared tools.",
        "builder": _build_general_context,
    },
}

ROLE_TASKS: dict[str, list[RoleTaskT]] = {
    "staff": [
        {
            "label": "My profile",
            "route_name": "account_profile",
            "key": "profile",
            "icon": "bi-person-badge",
        }
    ],
    "faculty": [
        {
            "label": "Teaching overview",
            "route_name": "staff_role_dashboard",
            "args": ["faculty"],
            "icon": "bi-journal-text",
        },
        {
            "label": "Grade tasks",
            "route_name": "faculty_grade_sections",
            "key": "faculty_grades",
            "icon": "bi-pencil-square",
        },
    ],
    "chair": [
        {
            "label": "Curricula",
            "route_name": "staff_role_dashboard",
            "args": ["chair"],
            "icon": "bi-diagram-3",
        },
        {
            "label": "Faculty workload",
            "route_name": "staff_role_dashboard",
            "args": ["chair"],
            "icon": "bi-people",
        },
        {
            "label": "Grade rosters",
            "route_name": "staff_grade_rosters",
            "args": ["chair"],
            "key": "grade_rosters",
            "icon": "bi-card-checklist",
        },
    ],
    "dean": [
        {
            "label": "Curriculum review",
            "route_name": "dean_curricula",
            "icon": "bi-diagram-3",
            "key": "curricula",
        },
        {
            "label": "Approval queue",
            "route_name": "staff_role_dashboard",
            "args": ["dean"],
            "icon": "bi-inbox",
        },
        {
            "label": "College chairs",
            "route_name": "staff_role_dashboard",
            "args": ["dean"],
            "icon": "bi-person-lines-fill",
        },
        {
            "label": "Grade rosters",
            "route_name": "staff_grade_rosters",
            "args": ["dean"],
            "key": "grade_rosters",
            "icon": "bi-card-checklist",
        },
    ],
    "vpaa": [
        {
            "label": "Institution approvals",
            "route_name": "vpaa_approvals",
            "icon": "bi-check2-square",
            "key": "approvals",
        },
        {
            "label": "Grade rosters",
            "route_name": "staff_grade_rosters",
            "args": ["vpaa"],
            "key": "grade_rosters",
            "icon": "bi-card-checklist",
        },
    ],
    "registrar": [
        {
            "label": "Transcript queue",
            "route_name": "staff_role_dashboard",
            "args": ["registrar"],
            "icon": "bi-file-earmark-text",
        },
        {
            "label": "Grade review",
            "route_name": "reg_grades_dashboard",
            "icon": "bi-card-checklist",
            "key": "grades",
        },
    ],
    "reg_officer": [
        {
            "label": "Semester windows",
            "route_name": "reg_crs_wins",
            "icon": "bi-calendar-event",
            "key": "semester_windows",
        },
        {
            "label": "Grade review",
            "route_name": "reg_grades_dashboard",
            "icon": "bi-card-checklist",
            "key": "grades",
        },
    ],
    "enrollment": [
        {
            "label": "Student directory",
            "route_name": "std_list",
            "icon": "bi-list-check",
            "key": "student_directory",
        },
        {
            "label": "Student lookup",
            "route_name": "std_admin_edit",
            "icon": "bi-search",
            "key": "student_lookup",
        },
        {
            "label": "Create student",
            "route_name": "create_std",
            "icon": "bi-person-plus",
            "key": "create_student",
        },
    ],
    "enrollment_officer": [
        {
            "label": "Student directory",
            "route_name": "std_list",
            "icon": "bi-list-check",
            "key": "student_directory",
        },
        {
            "label": "Student lookup",
            "route_name": "std_admin_edit",
            "icon": "bi-search",
            "key": "student_lookup",
        },
        {
            "label": "Create student",
            "route_name": "create_std",
            "icon": "bi-person-plus",
            "key": "create_student",
        },
    ],
    "finance": [
        {
            "label": "Finance overview",
            "route_name": "staff_role_dashboard",
            "args": ["finance"],
            "icon": "bi-cash-coin",
        }
    ],
    "cashier": [
        {
            "label": "Payment station",
            "route_name": "staff_role_dashboard",
            "args": ["cashier"],
            "icon": "bi-receipt",
        }
    ],
    "finance_officer": [
        {
            "label": "Finance overview",
            "route_name": "staff_role_dashboard",
            "args": ["finance_officer"],
            "icon": "bi-cash-coin",
        },
        {
            "label": "Invoice console",
            "route_name": "finance_officer_invoices",
            "icon": "bi-receipt-cutoff",
            "key": "invoice_console",
        },
        {
            "label": "Payment validation",
            "route_name": "finance_officer_invoices",
            "icon": "bi-shield-check",
            "key": "payment_validation",
            "query": "?tab=payments",
        },
    ],
    "scholarship": [
        {
            "label": "Beneficiary alerts",
            "route_name": "staff_role_dashboard",
            "args": ["scholarship"],
            "icon": "bi-award",
        }
    ],
    "donor": [
        {
            "label": "Sponsorship summary",
            "route_name": "staff_role_dashboard",
            "args": ["donor"],
            "icon": "bi-award",
        }
    ],
    "it": [
        {
            "label": "Support overview",
            "route_name": "staff_role_dashboard",
            "args": ["it"],
            "icon": "bi-tools",
        }
    ],
    "general": [
        {
            "label": "My profile",
            "route_name": "account_profile",
            "key": "profile",
            "icon": "bi-person-badge",
        }
    ],
}

EXPLICIT_ROLE_PARENT_EDGES: tuple[RoleEdgeT, ...] = (
    ("chair", "dean"),
    ("faculty", "chair"),
    ("dean", "vpaa"),
    ("registrar", "reg_officer"),
)


def _officer_parent_edges(role_slugs: Iterable[RoleSlugT]) -> tuple[RoleEdgeT, ...]:
    """Return role-parent edges where officer roles inherit base workspaces."""
    slugs = frozenset(role_slugs)
    return tuple(
        (base, slug)
        for slug in slugs
        if slug.endswith("_officer")
        for base in (slug[: -len("_officer")],)
        if base in slugs
    )


def _build_role_parent_map(config: RoleConfigMapT) -> RoleParentMapT:
    """Build the typed map of role -> parent roles allowed to access it."""
    parents: dict[RoleSlugT, set[RoleSlugT]] = {slug: set() for slug in config}
    edges = (*_officer_parent_edges(config), *EXPLICIT_ROLE_PARENT_EDGES)
    for child_slug, parent_slug in edges:
        if child_slug in parents and parent_slug in parents:
            parents[child_slug].add(parent_slug)
    return {slug: frozenset(values) for slug, values in parents.items()}


def _build_role_child_map(parent_map: RoleParentMapT) -> RoleChildMapT:
    """Invert the role-parent map into parent -> directly accessible roles."""
    children: dict[RoleSlugT, set[RoleSlugT]] = {slug: set() for slug in parent_map}
    for child_slug, parent_slugs in parent_map.items():
        for parent_slug in parent_slugs:
            children.setdefault(parent_slug, set()).add(child_slug)
    return {slug: frozenset(values) for slug, values in children.items()}


ROLE_INHERITANCE: RoleParentMapT = _build_role_parent_map(ROLE_CONFIG)
ROLE_CHILDREN: RoleChildMapT = _build_role_child_map(ROLE_INHERITANCE)

ROLE_ORDER: dict[str, int] = {slug: idx for idx, slug in enumerate(ROLE_PRIORITY)}
LOW_VALUE_SWITCHER_SLUGS: frozenset[RoleSlugT] = frozenset({"staff", "general"})


def _user_membership_slugs(user: User) -> set[str]:
    return {
        slug
        for slug, config in ROLE_CONFIG.items()
        if config["groups"] and _user_has_membership(user, slug)
    }


def _role_access_closure(role_slugs: Iterable[RoleSlugT]) -> set[RoleSlugT]:
    """Return every workspace reachable from the direct role memberships."""
    accessible = set(role_slugs)
    frontier = list(accessible)
    # Expand until a fixed point so displayed workspaces match permission checks.
    while frontier:
        role_slug = frontier.pop()
        for child_slug in ROLE_CHILDREN.get(role_slug, frozenset()):
            if child_slug in accessible:
                continue
            accessible.add(child_slug)
            frontier.append(child_slug)
    return accessible


def _accessible_role_slugs(user: User) -> set[str]:
    if user.is_superuser:
        slugs = set(ROLE_CONFIG.keys())
        if len(slugs) > 1:
            slugs.discard("general")
        return slugs
    membership = _user_membership_slugs(user)
    slugs = _role_access_closure(membership)
    if not slugs:
        return {"general"}
    return slugs


def _build_accessible_dashboard_links(
    user: User, active_slug: str
) -> list[DashboardLinkT]:
    slugs = _accessible_role_slugs(user)
    ordered = sorted(slugs, key=lambda slug: ROLE_ORDER.get(slug, len(ROLE_PRIORITY)))
    links: list[DashboardLinkT] = []
    for slug in ordered:
        config = ROLE_CONFIG.get(slug)
        if not config:
            continue
        if slug == "staff":
            href = reverse("account_profile")
        elif slug == "general":
            href = reverse("staff_dashboard")
        else:
            href = reverse("staff_role_dashboard", args=[slug])
        links.append(
            {
                "label": config.get("title", slug.replace("_", " ").title()),
                "summary": config.get("summary", ""),
                "href": href,
                "active": slug == active_slug,
                "slug": slug,
            }
        )
    return links


def build_staff_role_switcher(user: User, active_slug: str) -> list[RoleSwitcherLinkT]:
    """Return role-switching links for the shared staff sidebar."""
    accessible_links = [
        link
        for link in _build_accessible_dashboard_links(user, active_slug)
        if link["slug"] not in LOW_VALUE_SWITCHER_SLUGS
    ]
    if len(accessible_links) <= 1:
        return []
    return [
        {
            "label": link["label"],
            "href": link["href"],
            "active": link["active"],
        }
        for link in accessible_links
    ]


def _dashboard_href_for_role(role_slug: str) -> str:
    """Return the canonical dashboard URL for a staff sidebar."""
    if role_slug in {"staff", "general"}:
        return reverse("staff_dashboard")
    return reverse("staff_role_dashboard", args=[role_slug])


def build_staff_sidebar_links(
    role_slug: str, active_key: str = "overview"
) -> list[SidebarLinkT]:
    """Build task-oriented staff navigation for the portal sidebar."""
    tasks = ROLE_TASKS.get(role_slug, ROLE_TASKS["general"])
    dashboard_href = _dashboard_href_for_role(role_slug)
    links: list[SidebarLinkT] = [
        {
            "label": "Dashboard",
            "href": dashboard_href,
            "active": active_key == "overview",
            "icon": "bi-speedometer2",
        }
    ]
    seen_hrefs = {dashboard_href}
    for index, task in enumerate(tasks):
        task_key = task.get("key") or ("overview" if index == 0 else task["label"])
        href = _maybe_reverse(task["route_name"], args=task.get("args"))
        if not href:
            continue
        query = task.get("query", "")
        if query:
            href = f"{href}{query}"
        if href in seen_hrefs:
            continue
        seen_hrefs.add(href)
        links.append(
            {
                "label": task["label"],
                "href": href,
                "active": task_key == active_key,
                "icon": task["icon"],
            }
        )
    return links


def _user_has_membership(user: User, role_slug: str) -> bool:
    config = ROLE_CONFIG.get(role_slug)
    if not config or not config["groups"]:
        return False
    return bool(_user_gp_names(user).intersection(config["groups"]))


def user_can_access_role(user: User | AnonymousUser, role_slug: str) -> bool:
    """Return True when a user may open a staff workspace."""
    user = _as_user(user)
    config = ROLE_CONFIG.get(role_slug)
    if not config:
        return False
    if user.is_superuser:
        return True
    if not config["groups"]:
        return True
    return role_slug in _accessible_role_slugs(user)


def resolve_staff_role(user: User | AnonymousUser) -> str:
    """Resolve the highest-priority staff role for a user."""
    user = _as_user(user)
    group_names = _user_gp_names(user)
    for slug in ROLE_PRIORITY:
        config = ROLE_CONFIG.get(slug)
        if not config:
            continue
        config_groups = config["groups"]
        if not config_groups and slug == "general":
            continue
        if group_names.intersection(config_groups):
            return slug
    return "general"


__all__ = [
    "ROLE_CHILDREN",
    "ROLE_CONFIG",
    "ROLE_INHERITANCE",
    "ROLE_ORDER",
    "ROLE_PRIORITY",
    "ROLE_TASKS",
    "build_staff_role_switcher",
    "build_staff_sidebar_links",
    "resolve_staff_role",
    "user_can_access_role",
]
