"""Staff dashboards broken down by role."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render

from app.academics.models.curriculum import Curriculum
from app.finance.models.invoice import Invoice
from app.finance.models.payment import Payment
from app.finance.models.scholarship import (
    ScholarshipLetterTemplate,
    ScholarshipTermSnapshot,
)
from app.people.models.faculty import Faculty, FacultyWorkloadSnapshot
from app.registry.models.grade import Grade
from app.registry.models.registration import Registration
from app.registry.models.transcript import TranscriptRequest
from app.shared.models import ApprovalQueue
from app.timetable.models.section import Section

ADMIN_PORTAL_GROUPS = {"System Administrator", "IT Support"}

ROLE_PRIORITY = [
    "vpaa",
    "dean",
    "registrar",
    "scholarship",
    "finance",
    "chair",
    "instructor",
    "general",
]


def _user_group_names(user) -> set[str]:
    return set(user.groups.values_list("name", flat=True))


def _get_faculty_profile(user) -> Faculty | None:
    staff = getattr(user, "staff", None)
    if not staff:
        return None
    try:
        return staff.faculty
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


def _build_instructor_context(request: HttpRequest) -> dict:
    faculty = _get_faculty_profile(request.user)
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
    faculty = _get_faculty_profile(request.user)
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

    curricula_items = [
        {
            "label": cur.code,
            "value": cur.title,
        }
        for cur in curricula[:6]
    ]
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
            {"label": "Registrations pending clearance", "value": registration_anomalies},
        ],
        "panels": [
            {
                "title": "Transcript queue",
                "items": transcript_items,
            }
        ],
        "actions": [],
    }


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
        "actions": [],
    }


def _build_general_context(_: HttpRequest) -> dict:
    return _empty_role_context("No specific dashboard is associated with this account.")


ROLE_CONFIG = {
    "instructor": {
        "groups": {"Instructor"},
        "title": "Instruction Hub",
        "summary": "Teaching schedule and grading tasks.",
        "builder": _build_instructor_context,
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
        "groups": {"VPAA"},
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
    "scholarship": {
        "groups": {"Scholarship Officer"},
        "title": "Scholarship Office",
        "summary": "Donor letters and GPA compliance snapshots.",
        "builder": _build_scholarship_context,
    },
    "finance": {
        "groups": {"Financial Officer", "Cashier"},
        "title": "Finance & Holds",
        "summary": "Invoice tracking and payment validation.",
        "builder": _build_finance_context,
    },
    "general": {
        "groups": set(),
        "title": "Staff Workspace",
        "summary": "Common entry point for shared tools.",
        "builder": _build_general_context,
    },
}


def _resolve_staff_role(user) -> str:
    group_names = _user_group_names(user)
    for slug in ROLE_PRIORITY:
        config_groups = ROLE_CONFIG[slug]["groups"]
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
    base = {
        "title": config["title"],
        "summary": config["summary"],
        "role_slug": role_slug,
    }
    base.update(context)
    template_name = config.get("template", "website/staff/role_dashboard.html")
    return render(request, template_name, base)


@login_required
def staff_dashboard(request: HttpRequest) -> HttpResponse:
    """Route staff users to their highest-priority dashboard."""
    role_slug = _resolve_staff_role(request.user)
    return _render_role_dashboard(request, role_slug)


@login_required
def staff_role_dashboard(request: HttpRequest, role: str) -> HttpResponse:
    """Allow explicit navigation to a staff dashboard, enforcing membership."""
    if role not in ROLE_CONFIG:
        raise Http404("Unknown staff role.")

    config = ROLE_CONFIG[role]
    requires_membership = bool(config["groups"])
    lacks_group = not _user_group_names(request.user).intersection(config["groups"])
    if requires_membership and not request.user.is_superuser and lacks_group:
        raise PermissionDenied("You do not belong to this staff group.")

    return _render_role_dashboard(request, role)
