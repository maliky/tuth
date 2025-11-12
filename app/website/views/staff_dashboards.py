"""Staff dashboards broken down by role."""

from __future__ import annotations

from typing import Any, Callable, TypedDict, cast

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import NoReverseMatch, reverse

from app.academics.models.curriculum import Curriculum
from app.finance.models.invoice import Invoice
from app.finance.models.payment import Payment
from app.finance.models.scholarship import (
    ScholarshipLetterTemplate,
    ScholarshipTermSnapshot,
)
from app.people.models.faculty import Faculty, FacultyWorkloadSnapshot
from app.people.models.student import Student
from app.registry.models.document import DocumentStudent
from app.registry.models.grade import Grade
from app.registry.models.registration import Registration
from app.registry.models.transcript import TranscriptRequest
from app.shared.models import ApprovalQueue
from app.timetable.models.section import Section

ADMIN_PORTAL_GROUPS = {"System Administrator", "IT Support"}

ROLE_PRIORITY: list[str] = [
    "vpaa",
    "dean",
    "chair",
    "faculty",
    "registrar_officer",
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


class RoleConfig(TypedDict, total=False):
    groups: set[str]
    title: str
    summary: str
    builder: Callable[[HttpRequest], dict[str, Any]]
    template: str


def _as_user(user: User | AnonymousUser) -> User:
    """Narrow request.user to the concrete User type."""
    return cast(User, user)


def _user_group_names(user: User) -> set[str]:
    return set(user.groups.values_list("name", flat=True))


def _get_faculty_profile(user: User) -> Faculty | None:
    staff = getattr(user, "staff", None)
    if not staff:
        return None
    try:
        return cast(Faculty, staff.faculty)
    except Faculty.DoesNotExist:
        return None


def _empty_role_context(message: str) -> dict[str, list]:
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
    name: str, args: list | tuple | None = None, kwargs: dict | None = None
) -> str:
    try:
        return reverse(name, args=args, kwargs=kwargs)
    except NoReverseMatch:
        return ""


def _with_actions(context: dict[str, Any], extra: list[dict[str, Any]]) -> dict[str, Any]:
    merged = dict(context)
    merged_actions = list(context.get("actions", []))  # type: ignore[arg-type]
    merged_actions.extend(extra)
    merged["actions"] = merged_actions
    return merged


def _build_staff_context(request: HttpRequest) -> dict:
    user = _as_user(request.user)
    staff_profile = getattr(user, "staff", None)
    metrics = [{"label": "Username", "value": user.username}]
    if staff_profile and staff_profile.employment_date:
        metrics.append(
            {
                "label": "Employment start",
                "value": staff_profile.employment_date.strftime("%b %d, %Y"),
            }
        )

    profile_items = (
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

    actions = []
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


def _build_faculty_context(request: HttpRequest) -> dict:
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

    panel_items = [
        {
            "label": sec.curriculum_course.course.short_code,
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


def _build_chair_context(request: HttpRequest) -> dict:
    faculty = _get_faculty_profile(_as_user(request.user))
    if not faculty or not faculty.college:
        return _empty_role_context("No college associated to this chair account.")

    curricula = Curriculum.objects.filter(college=faculty.college).order_by("code")
    workloads = (
        FacultyWorkloadSnapshot.objects.filter(faculty__college=faculty.college)
        .select_related("faculty", "semester")
        .order_by("-semester__academic_year__start_date", "-semester__number")[:5]
    )
    workload_items = [
        {
            "label": f"{snap.faculty.staff_profile.long_name}",
            "value": f"{snap.semester}: {snap.credit_hours_delivered} ch",
            "meta": "Overload" if snap.overload_flag else "",
        }
        for snap in workloads
    ] or [{"label": "No workloads captured", "value": "Snapshots pending."}]

    curricula_items = []
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

    return {
        "metrics": [
            {"label": "Active curricula", "value": curricula.count()},
            {"label": "Faculty snapshots", "value": len(workload_items)},
        ],
        "panels": [
            {
                "title": "Curricula",
                "items": curricula_items,
            },
            {"title": "Recent workloads", "items": workload_items},
        ],
        "actions": [],
    }


def _build_dean_context(request: HttpRequest) -> dict:
    approvals_qs = ApprovalQueue.objects.filter(target_role="dean").order_by(
        "-created_at"
    )
    approvals = list(approvals_qs[:6])
    approval_items = [
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

    return {
        "metrics": [
            {"label": "Requests awaiting review", "value": approvals_qs.count()},
        ],
        "panels": [
            {
                "title": "Approval queue",
                "items": approval_items,
            }
        ],
        "actions": [],
    }


def _build_vpaa_context(_: HttpRequest) -> dict:
    approvals_qs = ApprovalQueue.objects.filter(target_role="vpaa").order_by(
        "-created_at"
    )
    approvals = list(approvals_qs[:8])
    approval_items = [
        {
            "label": approval.get_request_type_display(),
            "value": approval.status.title(),
            "meta": approval.payload.get("summary", ""),
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


def _build_enrollment_context(_: HttpRequest) -> dict:
    students_qs = Student.objects.select_related("curriculum")
    total_students = students_qs.count()
    onboarding = students_qs.filter(current_enrolled_semester__isnull=True).count()
    pending_docs = DocumentStudent.objects.filter(status__code="pending").count()
    recent_students = list(students_qs.order_by("-id")[:6])
    student_items = [
        {
            "label": student.long_name,
            "value": student.curriculum.short_name if student.curriculum else "--",
            "meta": student.student_id,
        }
        for student in recent_students
    ] or [
        {
            "label": "No students yet",
            "value": "Add your first profile to get started.",
        }
    ]

    actions = [
        {
            "label": "Student snapshot",
            "href": reverse("student_list"),
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
            "href": reverse("student_admin_edit"),
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


def _build_enrollment_officer_context(request: HttpRequest) -> dict:
    context = _build_enrollment_context(request)
    bulk_url = _maybe_reverse("admin:people_student_changelist")
    extras = []
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


def _build_registrar_context(_: HttpRequest) -> dict:
    pending_qs = TranscriptRequest.objects.filter(status__code="pending")
    pending_transcripts = list(
        pending_qs.select_related("student").order_by("-requested_at")[:8]
    )
    registration_anomalies = Registration.objects.filter(status__code="pending").count()
    transcript_items = [
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
        "actions": [],
    }


def _build_registrar_officer_context(request: HttpRequest) -> dict:
    base = _build_registrar_context(request)
    extras = [
        {
            "label": "Manage semester windows",
            "href": reverse("registrar_course_windows"),
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


def _build_scholarship_context(_: HttpRequest) -> dict:
    low_gpa = ScholarshipTermSnapshot.objects.filter(gpa__lt=2.5).select_related(
        "student", "semester"
    )
    templates = ScholarshipLetterTemplate.objects.filter(is_active=True)
    beneficiary_items = [
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


def _build_finance_context(_: HttpRequest) -> dict:
    pending_payments = Payment.objects.filter(status__code="pending").count()
    invoice_count = Invoice.objects.count()
    actions = []
    invoice_admin = _maybe_reverse("admin:finance_invoice_changelist")
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


def _build_cashier_context(request: HttpRequest) -> dict:
    base = _build_finance_context(request)
    quick_entry = _maybe_reverse("admin:finance_payment_add")
    extras: list[dict] = []
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


def _build_finance_officer_context(request: HttpRequest) -> dict:
    base = _build_finance_context(request)
    scholarship_admin = _maybe_reverse("admin:finance_scholarship_changelist")
    extras = []
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


def _build_it_context(_: HttpRequest) -> dict:
    return _empty_role_context(
        "IT support tasks live in the Django admin and infrastructure tools."
    )


def _build_general_context(_: HttpRequest) -> dict:
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
        "builder": _build_registrar_context,
    },
    "registrar_officer": {
        "groups": {"Registrar Officer"},
        "title": "Registrar Officer Console",
        "summary": "Semester windows and official roster controls.",
        "builder": _build_registrar_officer_context,
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

ROLE_INHERITANCE: dict[str, set[str]] = {}
for slug in ROLE_CONFIG:
    if slug.endswith("_officer"):
        base = slug[: -len("_officer")]
        ROLE_INHERITANCE.setdefault(base, set()).add(slug)


def _user_has_membership(user: User, role_slug: str) -> bool:
    config = ROLE_CONFIG.get(role_slug)
    if not config or not config["groups"]:
        return False
    return bool(_user_group_names(user).intersection(config["groups"]))


def _user_inherits_role(user: User, role_slug: str) -> bool:
    inherited = ROLE_INHERITANCE.get(role_slug, set())
    return any(_user_has_membership(user, slug) for slug in inherited)


def _resolve_staff_role(user: User) -> str:
    group_names = _user_group_names(user)
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
    base: dict[str, Any] = {
        "title": config["title"],
        "summary": config["summary"],
        "role_slug": role_slug,
        "page_title": config["title"],
        "page_summary": config["summary"],
        "eyebrow": role_slug.replace("_", " ").title(),
    }
    base.update(context)
    template_name = config.get("template", "website/staff/role_dashboard.html")

    sidebar_links = [
        {
            "label": "Dashboard",
            "href": reverse("staff_dashboard"),
            "active": role_slug == "general",
            "icon": "bi-speedometer2",
        },
        {
            "label": "Roles",
            "href": reverse("staff_role_dashboard", args=[role_slug]),
            "active": role_slug != "general",
            "icon": "bi-people",
        },
    ]
    breadcrumbs = [
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
    config = ROLE_CONFIG[role]
    requires_membership = bool(config["groups"])
    has_access = (
        user.is_superuser
        or not requires_membership
        or _user_has_membership(user, role)
        or _user_inherits_role(user, role)
    )
    if not has_access:
        raise PermissionDenied("You do not belong to this staff group.")

    return _render_role_dashboard(request, role)
