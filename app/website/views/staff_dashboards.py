"""Staff dashboards broken down by role."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any, NotRequired, TypeAlias, TypedDict, cast

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import NoReverseMatch, reverse

from app.academics.models.curriculum import Curriculum
from app.finance.models.invoice import CrsInvoice
from app.finance.models.payment import Payment
from app.finance.models.scholarship import (
    ScholarshipLetterTemplate,
    ScholarshipTermSnapshot,
)
from app.people.models.faculty import Faculty, FacultyWorkloadSnapshot
from app.people.models.student import Student
from app.registry.models.document import DocStd
from app.registry.models.grade import Grade
from app.registry.models.registration import Registration
from app.registry.models.transcript import TranscriptRequest
from app.shared.auth.perms import UserRole
from app.shared.models import ApprovalQueue
from app.timetable.models.section import Section

ADMIN_PORTAL_GROUPS = {"System Administrator", "IT Support"}

DisplayValueT: TypeAlias = str | int | float | bool | None
RoleSlugT: TypeAlias = str
RoleEdgeT: TypeAlias = tuple[RoleSlugT, RoleSlugT]

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
    "it",
    "staff",
    "general",
]


class MetricT(TypedDict):
    label: str
    value: DisplayValueT


class PanelItemT(TypedDict):
    label: str
    value: DisplayValueT
    meta: NotRequired[str]


class PanelT(TypedDict):
    title: str
    items: list[PanelItemT]
    subtitle: NotRequired[str]


class ActionT(TypedDict):
    label: str
    href: str
    description: str
    variant: str
    is_admin: NotRequired[bool]


class RoleContextT(TypedDict):
    metrics: list[MetricT]
    panels: list[PanelT]
    actions: list[ActionT]


class DashboardLinkT(TypedDict):
    label: str
    summary: str
    href: str
    active: bool
    slug: str


class RoleSwitcherLinkT(TypedDict):
    label: str
    href: str
    active: bool


class SidebarLinkT(TypedDict):
    label: str
    href: str
    active: bool
    icon: str


class RoleTaskT(TypedDict):
    label: str
    route_name: str
    icon: str
    args: NotRequired[list[str]]
    key: NotRequired[str]
    query: NotRequired[str]


class BreadcrumbT(TypedDict):
    label: str
    href: str


class RoleConfig(TypedDict, total=False):
    groups: set[str]
    title: str
    summary: str
    builder: Callable[[HttpRequest], RoleContextT]
    template: str


RoleConfigMapT: TypeAlias = Mapping[RoleSlugT, RoleConfig]
RoleParentMapT: TypeAlias = dict[RoleSlugT, frozenset[RoleSlugT]]
RoleChildMapT: TypeAlias = dict[RoleSlugT, frozenset[RoleSlugT]]


def _as_user(user: User | AnonymousUser) -> User:
    """Narrow request.user to the concrete User type."""
    return cast(User, user)


def _user_gp_names(user: User) -> set[str]:
    return set(user.groups.values_list("name", flat=True))


def _get_faculty_profile(user: User) -> Faculty | None:
    staff = getattr(user, "staff", None)
    if not staff:
        return None
    try:
        return cast(Faculty, staff.faculty)
    except Faculty.DoesNotExist:
        return None


def _empty_role_context(message: str) -> RoleContextT:
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


def _maybe_reverse(
    name: str,
    args: Sequence[object] | None = None,
    kwargs: dict[str, object] | None = None,
) -> str:
    try:
        return reverse(name, args=args, kwargs=kwargs)
    except NoReverseMatch:
        return ""


def _with_actions(context: RoleContextT, extra: list[ActionT]) -> RoleContextT:
    """Return a role context with additional actions."""
    return {
        "metrics": list(context["metrics"]),
        "panels": list(context["panels"]),
        "actions": [*context["actions"], *extra],
    }


def _annotate_admin_actions(actions: list[ActionT]) -> list[ActionT]:
    """Flag action links that point to Django admin views."""
    admin_prefix = reverse("admin:index")
    annotated: list[ActionT] = []
    for action in actions:
        href = str(action.get("href") or "")
        is_admin = href.startswith(admin_prefix)
        annotated.append(
            {
                **action,
                "is_admin": is_admin,
                # Align action button colors with admin vs app destinations.
                "variant": "primary" if is_admin else "warning",
            }
        )
    return annotated


def _build_staff_context(request: HttpRequest) -> RoleContextT:
    user = _as_user(request.user)
    staff_profile = getattr(user, "staff", None)
    metrics: list[MetricT] = [{"label": "Username", "value": user.username}]
    if staff_profile and staff_profile.employment_date:
        metrics.append(
            {
                "label": "Employment start",
                "value": staff_profile.employment_date.strftime("%b %d, %Y"),
            }
        )

    profile_items: list[PanelItemT] = (
        [
            {
                "label": "Staff ID",
                "value": staff_profile.staff_id,
                "meta": staff_profile.position or "",
            },
            {
                "label": "Department",
                "value": str(staff_profile.department or "Unassigned"),
                "meta": staff_profile.division or "",
            },
            {"label": "Contact email", "value": user.email or "Not set"},
        ]
        if staff_profile
        else [
            {
                "label": "No staff profile",
                "value": "Ask HR to complete your onboarding record.",
            }
        ]
    )

    actions: list[ActionT] = []
    if staff_profile:
        edit_url = _maybe_reverse("admin:people_staff_change", args=[staff_profile.pk])
        if edit_url:
            actions.append(
                {
                    "label": "Edit my staff profile",
                    "href": edit_url,
                    "description": "Update contact information or department details.",
                    "variant": "outline-primary",
                }
            )

    return {
        "metrics": metrics,
        "panels": [{"title": "Profile", "items": profile_items}],
        "actions": actions,
    }


def _build_faculty_context(request: HttpRequest) -> RoleContextT:
    faculty = _get_faculty_profile(_as_user(request.user))
    if not faculty:
        return _empty_role_context("No faculty profile linked to this account yet.")

    sections_qs = Section.objects.filter(faculty=faculty).select_related(
        "semester", "curriculum_course__course"
    )
    upcoming_sections = list(
        sections_qs.order_by(
            "semester__academic_year__start_date", "semester__number", "number"
        )[:5]
    )
    pending_grades = Grade.objects.filter(
        section__faculty=faculty, value__isnull=True
    ).count()

    panel_items: list[PanelItemT] = [
        {
            "label": sec.curriculum_course.course.short_code
            or sec.curriculum_course.course.title
            or "Course",
            "value": f"{sec.semester} · Section {sec.number}",
            "meta": f"Seats: {sec.current_registrations}/{sec.max_seats}",
        }
        for sec in upcoming_sections
    ] or [{"label": "No sections yet", "value": "Teaching assignments not published."}]

    return {
        "metrics": [
            {"label": "Sections assigned", "value": sections_qs.count()},
            {"label": "Pending grade updates", "value": pending_grades},
        ],
        "panels": [{"title": "Upcoming sections", "items": panel_items}],
        "actions": [],
    }


def _build_chair_context(request: HttpRequest) -> RoleContextT:
    faculty = _get_faculty_profile(_as_user(request.user))
    if not faculty or not faculty.college:
        return _empty_role_context("No college associated to this chair account.")

    curricula = Curriculum.objects.filter(college=faculty.college).order_by("code")
    workloads = (
        FacultyWorkloadSnapshot.objects.filter(faculty__college=faculty.college)
        .select_related("faculty", "semester")
        .order_by("-semester__academic_year__start_date", "-semester__number")[:5]
    )
    workload_items: list[PanelItemT] = [
        {
            "label": f"{snap.faculty.staff_profile.long_name}",
            "value": f"{snap.semester}: {snap.credit_hours_delivered} ch",
            "meta": "Overload" if snap.overload_flag else "",
        }
        for snap in workloads
    ] or [{"label": "No workloads captured", "value": "Snapshots pending."}]

    curricula_items: list[PanelItemT] = []
    for cur in curricula[:6]:
        curricula_items.append(
            {
                "label": cur.short_name,
                "value": cur.long_name or cur.short_name,
            }
        )
    if not curricula_items:
        curricula_items = [
            {"label": "No curricula", "value": "Assign one to this college."},
        ]

    department = faculty.staff_profile.department
    department_faculty_items: list[PanelItemT] = []
    if department:
        department_faculty = (
            Faculty.objects.filter(staff_profile__department=department)
            .exclude(staff_profile=faculty.staff_profile)
            .select_related("staff_profile__department")
            .order_by("staff_profile__user__last_name")
        )
        for member in department_faculty[:6]:
            department_faculty_items.append(
                {
                    "label": member.staff_profile.long_name,
                    "value": member.staff_profile.position or "Faculty",
                    "meta": str(member.staff_profile.department or "Department"),
                }
            )
        if not department_faculty_items:
            department_faculty_items = [
                {
                    "label": "No other faculty yet",
                    "value": "Invite colleagues to teach for this department.",
                }
            ]
    else:
        department_faculty_items = [
            {
                "label": "Department not assigned",
                "value": "Ask HR to link your profile to a department first.",
            }
        ]

    panels: list[PanelT] = [
        {
            "title": "Curricula",
            "items": curricula_items,
        },
        {"title": "Recent workloads", "items": workload_items},
        {
            "title": "Department faculty",
            "items": department_faculty_items,
        },
    ]

    return {
        "metrics": [
            {"label": "Active curricula", "value": curricula.count()},
            {"label": "Faculty snapshots", "value": len(workload_items)},
        ],
        "panels": panels,
        "actions": [],
    }


def _build_dean_context(request: HttpRequest) -> RoleContextT:
    faculty_profile = _get_faculty_profile(_as_user(request.user))
    college = faculty_profile.college if faculty_profile else None
    approvals_qs = ApprovalQueue.objects.filter(target_role="dean").order_by(
        "-created_at"
    )
    approvals = list(approvals_qs[:6])
    approval_items: list[PanelItemT] = [
        {
            "label": approval.get_request_type_display(),
            "value": approval.status.title(),
            "meta": approval.created_at.strftime("%d %b %Y"),
        }
        for approval in approvals
    ]
    if not approval_items:
        approval_items = [
            {"label": "No requests", "value": "You're all caught up."},
        ]

    chairs_items: list[PanelItemT] = []
    if college:
        chairs = (
            Faculty.objects.filter(
                college=college,
                staff_profile__user__groups__name=UserRole.CHAIR.value.label,
            )
            .select_related("staff_profile__department")
            .order_by(
                "staff_profile__department__code",
                "staff_profile__user__last_name",
            )
        )
        for chair in chairs[:6]:
            chairs_items.append(
                {
                    "label": chair.staff_profile.long_name,
                    "value": chair.staff_profile.position or "Chair",
                    "meta": str(chair.staff_profile.department or "Department"),
                }
            )
    if not chairs_items:
        chairs_items = [
            {
                "label": "No chairs assigned",
                "value": "Ask HR to appoint department chairs for your college.",
            }
        ]

    return {
        "metrics": [
            {"label": "Requests awaiting review", "value": approvals_qs.count()},
        ],
        "panels": [
            {
                "title": "Approval queue",
                "items": approval_items,
            },
            {
                "title": "Chairs in my college",
                "items": chairs_items,
            },
        ],
        "actions": [],
    }


def _build_vpaa_context(_: HttpRequest) -> RoleContextT:
    approvals_qs = ApprovalQueue.objects.filter(target_role="vpaa").order_by(
        "-created_at"
    )
    approvals = list(approvals_qs[:8])
    approval_items: list[PanelItemT] = [
        {
            "label": approval.get_request_type_display(),
            "value": approval.status.title(),
            "meta": str(approval.payload.get("summary", "")),
        }
        for approval in approvals
    ]
    if not approval_items:
        approval_items = [
            {
                "label": "Queue is empty",
                "value": "No open curriculum or policy actions.",
            }
        ]

    return {
        "metrics": [
            {"label": "Pending approvals", "value": approvals_qs.count()},
        ],
        "panels": [
            {
                "title": "Items awaiting VPAA decision",
                "items": approval_items,
            }
        ],
        "actions": [],
    }


def _build_enrollment_context(_: HttpRequest) -> RoleContextT:
    students_qs = Student.objects.all()
    total_students = students_qs.count()
    onboarding = students_qs.filter(last_enrolled_semester__isnull=True).count()
    pending_docs = DocStd.objects.filter(status__code="pending").count()
    recent_students = list(students_qs.order_by("-id")[:6])
    student_items: list[PanelItemT] = [
        {
            "label": student.long_name,
            "value": student.primary_curriculum.short_name,
            "meta": student.student_id,
        }
        for student in recent_students
    ] or [
        {
            "label": "No students yet",
            "value": "Add your first profile to get started.",
        }
    ]

    actions: list[ActionT] = [
        {
            "label": "Student snapshot",
            "href": reverse("std_list"),
            "description": "Review the latest arrivals without leaving Tusis.",
            "variant": "outline-primary",
        },
        {
            "label": "Create student in admin",
            "href": reverse("admin:people_student_add"),
            "description": "Open the official admissions form with attachments and history.",
            "variant": "primary",
        },
        {
            "label": "Edit student in admin",
            "href": reverse("std_admin_edit"),
            "description": "Pick an ID and Tusis will send you straight to the admin edit screen.",
            "variant": "outline-secondary",
        },
    ]

    return {
        "metrics": [
            {"label": "Total students", "value": total_students},
            {"label": "Awaiting enrollment", "value": onboarding},
            {"label": "Docs pending", "value": pending_docs},
        ],
        "panels": [
            {
                "title": "Recently created",
                "items": student_items,
            }
        ],
        "actions": actions,
    }


def _build_enrollment_officer_context(request: HttpRequest) -> RoleContextT:
    context = _build_enrollment_context(request)
    bulk_url = _maybe_reverse("admin:people_student_changelist")
    extras: list[ActionT] = []
    if bulk_url:
        extras.append(
            {
                "label": "Open admin directory",
                "href": bulk_url,
                "description": "Search, filter, and export from Django admin.",
                "variant": "outline-secondary",
            }
        )
    return _with_actions(context, extras)


def _build_reg_context(_: HttpRequest) -> RoleContextT:
    pending_qs = TranscriptRequest.objects.filter(status__code="pending")
    pending_transcripts = list(
        pending_qs.select_related("student").order_by("-requested_at")[:8]
    )
    registration_anomalies = Registration.objects.filter(status__code="pending").count()
    transcript_items: list[PanelItemT] = [
        {
            "label": req.student.long_name,
            "value": req.destination_name,
            "meta": req.requested_at.strftime("%d %b %Y"),
        }
        for req in pending_transcripts
    ]
    if not transcript_items:
        transcript_items = [
            {"label": "No transcript requests", "value": "All clear."},
        ]

    actions: list[ActionT] = []
    grades_url = _maybe_reverse("reg_grades_dashboard")
    if grades_url:
        actions.append(
            {
                "label": "Review grades",
                "href": grades_url,
                "description": "Browse grades grouped by student and semester.",
                "variant": "outline-secondary",
            }
        )
    return {
        "metrics": [
            {"label": "Pending transcripts", "value": pending_qs.count()},
            {
                "label": "Registrations pending clearance",
                "value": registration_anomalies,
            },
        ],
        "panels": [
            {
                "title": "Transcript queue",
                "items": transcript_items,
            }
        ],
        "actions": actions,
    }


def _build_reg_officer_context(request: HttpRequest) -> RoleContextT:
    base = _build_reg_context(request)
    extras: list[ActionT] = [
        {
            "label": "Manage semester windows",
            "href": reverse("reg_crs_wins"),
            "description": "Open or close registration and grading periods.",
            "variant": "warning",
        }
    ]
    admin_url = _maybe_reverse("admin:timetable_semester_changelist")
    if admin_url:
        extras.append(
            {
                "label": "Review semester setup",
                "href": admin_url,
                "description": "Audit statuses directly in Django admin.",
                "variant": "outline-secondary",
            }
        )
    return _with_actions(base, extras)


def _build_scholarship_context(_: HttpRequest) -> RoleContextT:
    low_gpa = ScholarshipTermSnapshot.objects.filter(gpa__lt=2.5).select_related(
        "student", "semester"
    )
    templates = ScholarshipLetterTemplate.objects.filter(is_active=True)
    beneficiary_items: list[PanelItemT] = [
        {
            "label": snap.student.long_name,
            "value": f"GPA {snap.gpa}",
            "meta": str(snap.semester),
        }
        for snap in low_gpa[:6]
    ]
    if not beneficiary_items:
        beneficiary_items = [
            {
                "label": "All beneficiaries compliant",
                "value": "No GPA alerts this term.",
            }
        ]

    return {
        "metrics": [
            {"label": "Students < 2.5 GPA", "value": low_gpa.count()},
            {"label": "Active letter templates", "value": templates.count()},
        ],
        "panels": [
            {
                "title": "At-risk beneficiaries",
                "items": beneficiary_items,
            }
        ],
        "actions": [],
    }


def _build_finance_context(_: HttpRequest) -> RoleContextT:
    pending_payments = Payment.objects.filter(status__code="pending").count()
    invoice_count = CrsInvoice.objects.count()
    actions: list[ActionT] = []
    invoice_admin = _maybe_reverse("admin:finance_courseinvoice_changelist")
    if invoice_admin:
        actions.append(
            {
                "label": "Review invoices",
                "href": invoice_admin,
                "description": "Open the finance register filtered by status.",
                "variant": "outline-primary",
            }
        )
    payment_admin = _maybe_reverse("admin:finance_payment_changelist")
    if payment_admin:
        actions.append(
            {
                "label": "Validate payments",
                "href": payment_admin,
                "description": "Confirm proof of payment submissions.",
                "variant": "primary",
            }
        )
    return {
        "metrics": [
            {"label": "Outstanding invoices", "value": invoice_count},
            {"label": "Payments awaiting validation", "value": pending_payments},
        ],
        "panels": [
            {
                "title": "Next steps",
                "items": [
                    {
                        "label": "Reconcile proofs",
                        "value": "Verify supporting documents.",
                    },
                    {"label": "Release cleared holds", "value": "Unblock students."},
                ],
            }
        ],
        "actions": actions,
    }


def _build_cashier_context(request: HttpRequest) -> RoleContextT:
    base = _build_finance_context(request)
    quick_entry = _maybe_reverse("admin:finance_payment_add")
    extras: list[ActionT] = []
    if quick_entry:
        extras.append(
            {
                "label": "Record payment",
                "href": quick_entry,
                "description": "Jump straight to the cashier form in admin.",
                "variant": "success",
            }
        )
    return _with_actions(base, extras)


def _build_finance_officer_context(request: HttpRequest) -> RoleContextT:
    base = _build_finance_context(request)
    scholarship_admin = _maybe_reverse("admin:finance_scholarship_changelist")
    extras: list[ActionT] = []
    finance_console = _maybe_reverse("finance_officer_invoices")
    if finance_console:
        extras.append(
            {
                "label": "Invoice & payment console",
                "href": finance_console,
                "description": "Review invoices and record pending payments.",
                "variant": "primary",
            }
        )
    if scholarship_admin:
        extras.append(
            {
                "label": "Manage scholarships",
                "href": scholarship_admin,
                "description": "Adjust donor awards and compliance snapshots.",
                "variant": "outline-secondary",
            }
        )
    return _with_actions(base, extras)


def _build_it_context(_: HttpRequest) -> RoleContextT:
    return _empty_role_context(
        "IT support tasks live in the Django admin and infrastructure tools."
    )


def _build_general_context(_: HttpRequest) -> RoleContextT:
    return _empty_role_context("No specific dashboard is associated with this account.")


ROLE_CONFIG: dict[str, RoleConfig] = {
    "staff": {
        "groups": {"Staff"},
        "title": "My Staff Workspace",
        "summary": "Personal contact info and HR shortcuts.",
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
    "it": {
        "groups": {"IT", "IT Support"},
        "title": "IT Support",
        "summary": "Infrastructure, monitoring, and admin tooling.",
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
            "label": "My staff profile",
            "route_name": "staff_role_dashboard",
            "args": ["staff"],
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
            "route_name": "staff_role_dashboard",
            "args": ["faculty"],
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
    ],
    "dean": [
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
    ],
    "vpaa": [
        {
            "label": "Institution approvals",
            "route_name": "staff_role_dashboard",
            "args": ["vpaa"],
            "icon": "bi-check2-square",
        }
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
            "label": "Student snapshot",
            "route_name": "std_list",
            "icon": "bi-list-check",
            "key": "student_snapshot",
        },
        {
            "label": "Admin edit lookup",
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
            "label": "Student snapshot",
            "route_name": "std_list",
            "icon": "bi-list-check",
            "key": "student_snapshot",
        },
        {
            "label": "Admin edit lookup",
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
            "label": "Workspace home",
            "route_name": "staff_dashboard",
            "icon": "bi-speedometer2",
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
        if slug == "general":
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
    accessible_links = _build_accessible_dashboard_links(user, active_slug)
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


def build_staff_sidebar_links(
    role_slug: str, active_key: str = "overview"
) -> list[SidebarLinkT]:
    """Build task-oriented staff navigation for the portal sidebar."""
    tasks = ROLE_TASKS.get(role_slug, ROLE_TASKS["general"])
    links: list[SidebarLinkT] = []
    for index, task in enumerate(tasks):
        task_key = task.get("key") or ("overview" if index == 0 else task["label"])
        href = _maybe_reverse(task["route_name"], args=task.get("args"))
        if not href:
            continue
        query = task.get("query", "")
        if query:
            href = f"{href}{query}"
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


def _user_can_access_role(user: User, role_slug: str) -> bool:
    """Return True when a user may open a staff workspace."""
    config = ROLE_CONFIG.get(role_slug)
    if not config:
        return False
    if user.is_superuser:
        return True
    if not config["groups"]:
        return True
    return role_slug in _accessible_role_slugs(user)


def _resolve_staff_role(user: User) -> str:
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


def _render_role_dashboard(request: HttpRequest, role_slug: str) -> HttpResponse:
    config = ROLE_CONFIG.get(role_slug)
    if not config:
        raise Http404("Unknown staff dashboard.")
    context = config["builder"](request)
    accessible_links = _build_accessible_dashboard_links(
        _as_user(request.user), role_slug
    )
    role_switcher = build_staff_role_switcher(_as_user(request.user), role_slug)
    base: dict[str, Any] = {
        "title": config["title"],
        "summary": config["summary"],
        "role_slug": role_slug,
        "page_title": config["title"],
        "page_summary": config["summary"],
        "eyebrow": role_slug.replace("_", " ").title(),
    }
    base.update(context)
    # Add admin cues for action cards before rendering.
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


@login_required
def staff_dashboard(request: HttpRequest) -> HttpResponse:
    """Route staff users to their highest-priority dashboard."""
    role_slug = _resolve_staff_role(_as_user(request.user))
    return _render_role_dashboard(request, role_slug)


@login_required
def staff_role_dashboard(request: HttpRequest, role: str) -> HttpResponse:
    """Allow explicit navigation to a staff dashboard, enforcing membership."""
    if role not in ROLE_CONFIG:
        raise Http404("Unknown staff role.")

    user = _as_user(request.user)
    if not _user_can_access_role(user, role):
        raise PermissionDenied("You do not belong to this staff group.")

    return _render_role_dashboard(request, role)
