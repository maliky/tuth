"""Staff role context builders for the shared portal dashboard."""

from __future__ import annotations

from django.http import HttpRequest
from django.urls import reverse

from app.academics.models.course import Course
from app.academics.models.curriculum import Curriculum
from app.academics.models.curriculum_course import CurriCrs
from app.finance.models.invoice import CrsInvoice
from app.finance.models.payment import Payment
from app.finance.registration_invoices import (
    missing_registration_invoice_counts,
)
from app.finance.models.scholarship import (
    Scholarship,
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
from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.semester import Semester
from app.timetable.models.section import Section
from app.website.services.portal_types import (
    ActionT,
    MetricT,
    PanelItemT,
    PanelT,
    RoleContextT,
)
from app.website.services.staff_common import (
    AdminModelShortcutSpecT,
    _as_user,
    _empty_role_context,
    _get_donor_profile,
    _get_faculty_profile,
    _admin_shortcuts_for_models,
    _maybe_reverse,
    _with_actions,
)

REGISTRAR_ADMIN_SHORTCUTS: tuple[AdminModelShortcutSpecT, ...] = (
    ("Students", Student),
    ("Registrations", Registration),
    ("Grades", Grade),
    ("Transcript requests", TranscriptRequest),
    ("Sections", Section),
    ("Semesters", Semester),
    ("Academic years", AcademicYear),
    ("Courses", Course),
    ("Curricula", Curriculum),
    ("Curriculum courses", CurriCrs),
)


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

    return {
        "metrics": metrics,
        "panels": [{"title": "Profile", "items": profile_items}],
        "actions": [],
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

    actions: list[ActionT] = []
    curricula_url = _maybe_reverse("dean_curricula")
    if curricula_url:
        actions.append(
            {
                "label": "Review curricula",
                "href": curricula_url,
                "description": "Review college curricula and request VPAA activation.",
                "variant": "primary",
            }
        )

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
        "actions": actions,
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

    actions: list[ActionT] = []
    approvals_url = _maybe_reverse("vpaa_approvals")
    if approvals_url:
        actions.append(
            {
                "label": "Open approval queue",
                "href": approvals_url,
                "description": "Review VPAA curriculum and policy requests.",
                "variant": "primary",
            }
        )

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
        "actions": actions,
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
            "label": "Create student",
            "href": reverse("create_std"),
            "description": "Capture a new student profile directly in Tusis.",
            "variant": "primary",
        },
        {
            "label": "Find student",
            "href": reverse("std_admin_edit"),
            "description": "Search by ID or name and open the portal profile.",
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
    return _build_enrollment_context(request)


def _build_reg_context(request: HttpRequest) -> RoleContextT:
    user = _as_user(request.user)
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
        "admin_shortcuts": _admin_shortcuts_for_models(
            user,
            REGISTRAR_ADMIN_SHORTCUTS,
        ),
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


def _build_donor_context(request: HttpRequest) -> RoleContextT:
    """Render a donor-facing sponsorship summary."""
    donor = _get_donor_profile(_as_user(request.user))
    if donor is None:
        return _empty_role_context("No donor profile is linked to this account yet.")

    scholarships = (
        Scholarship.objects.filter(donor=donor)
        .select_related("student")
        .order_by("-start_date", "-id")
    )
    templates_count = donor.letter_templates.filter(is_active=True).count()
    scholarship_items: list[PanelItemT] = [
        {
            "label": scholarship.student.long_name,
            "value": f"{scholarship.amount} from {scholarship.start_date:%d %b %Y}",
            "meta": scholarship.conditions or "No conditions recorded.",
        }
        for scholarship in scholarships[:6]
    ]
    if not scholarship_items:
        scholarship_items = [
            {
                "label": "No active sponsorships yet",
                "value": "Scholarship awards will appear here once recorded.",
            }
        ]

    return {
        "metrics": [
            {"label": "Sponsored students", "value": scholarships.count()},
            {"label": "Letter templates", "value": templates_count},
        ],
        "panels": [
            {
                "title": "Scholarship commitments",
                "items": scholarship_items,
            }
        ],
        "actions": [],
    }


def _build_finance_context(_: HttpRequest) -> RoleContextT:
    current_semester = Semester.get_current_sem()
    current_semester_id = current_semester.id if current_semester else None
    pending_payments = Payment.objects.filter(status__code="pending").count()
    invoice_count = CrsInvoice.objects.filter(balance__gt=0).count()
    # Scope dashboard work to the active billing semester; all-history scans are
    # kept for explicit reports, not every role-overview page load.
    missing_invoice_counts = missing_registration_invoice_counts(
        semester_id=current_semester_id
    )
    uninvoiced_count = missing_invoice_counts["billable"]
    fee_setup_count = missing_invoice_counts["fee_setup"]
    actions: list[ActionT] = []
    finance_console = _maybe_reverse("finance_officer_invoices")
    if finance_console:
        actions.append(
            {
                "label": "Open finance console",
                "href": finance_console,
                "description": "Review invoices and payment validation from Tusis.",
                "variant": "primary",
            }
        )
    return {
        "metrics": [
            {"label": "Outstanding invoices", "value": invoice_count},
            {"label": "Uninvoiced registrations", "value": uninvoiced_count},
            {"label": "Needs fee setup", "value": fee_setup_count},
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
    return _build_finance_context(request)


def _build_finance_officer_context(request: HttpRequest) -> RoleContextT:
    """Return the finance officer workspace without duplicate console links."""
    return _build_finance_context(request)


def _build_it_context(_: HttpRequest) -> RoleContextT:
    return _empty_role_context("IT support workflows are not yet exposed in the portal.")


def _build_general_context(_: HttpRequest) -> RoleContextT:
    return _empty_role_context("No specific dashboard is associated with this account.")


__all__ = [
    "_build_cashier_context",
    "_build_chair_context",
    "_build_dean_context",
    "_build_donor_context",
    "_build_enrollment_context",
    "_build_enrollment_officer_context",
    "_build_faculty_context",
    "_build_finance_context",
    "_build_finance_officer_context",
    "_build_general_context",
    "_build_it_context",
    "_build_reg_context",
    "_build_reg_officer_context",
    "_build_scholarship_context",
    "_build_staff_context",
    "_build_vpaa_context",
]
