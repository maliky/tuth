"""Website views for the student dashboard."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import cast

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth import logout
from django.contrib.auth.views import LoginView
from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.db.models import Avg, DecimalField, Prefetch, Q, Sum, Value, Count
from django.db.models.functions import Coalesce
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View

from app.academics.models.course import CurriculumCourse
from app.academics.models.curriculum import Curriculum
from app.academics.models.prerequisite import Prerequisite
from app.finance.models.invoice import Invoice
from app.finance.models.payment import Payment
from app.finance.models.scholarship import (
    ScholarshipLetterTemplate,
    ScholarshipTermSnapshot,
)
from app.people.models.faculty import Faculty, FacultyWorkloadSnapshot
from app.people.forms.person import StudentForm
from app.people.models.student import Student
from app.registry.models.grade import Grade
from app.registry.models.registration import Registration, RegistrationStatus
from app.registry.models.transcript import TranscriptRequest
from app.shared.models import ApprovalQueue
from app.shared.status import StatusHistory
from app.timetable.choices import WEEKDAYS_NUMBER
from app.timetable.models.semester import Semester, SemesterStatus
from app.timetable.models.section import Section
from app.timetable.utils import get_current_semester


def landing_page(request: HttpRequest) -> HttpResponse:
    """Render the website landing page."""
    return render(request, "website/landing.html")


def _require_student(user: User | AnonymousUser) -> Student:
    """Return the related Student or abort early."""
    student = getattr(user, "student", None)
    if student is None and not user.is_superuser:
        raise PermissionDenied("User has no Student profile.")
    return cast(Student, student)  # <— only cast once, in one place


def _resolve_semester(student: Student, requested_semester_id: str | None):
    """Return the semester that should drive course availability."""
    open_semesters = (
        Semester.objects.filter(status_id__in=Semester.REGISTRATION_OPEN_CODES)
        .select_related("academic_year", "status")
        .order_by("academic_year__start_date", "number")
    )
    semester: Semester | None = None
    if requested_semester_id:
        semester = next(
            (sem for sem in open_semesters if str(sem.id) == str(requested_semester_id)),
            None,
        )
    if semester is None and open_semesters:
        semester = open_semesters.first()
    if semester is None:
        semester = student.current_enrolled_semester or get_current_semester()
    return semester, list(open_semesters)


def course_dashboard(request: HttpRequest) -> HttpResponse:
    """Allow a student to manage their course registrations."""
    # rely on the authenticated user's Student profile
    student = _require_student(request.user)
    if request.method == "POST":
        action = request.POST.get("action")

        if action == "add":
            section_id = request.POST.get("section_id")
            section = get_object_or_404(Section, pk=section_id)
            Registration.objects.create(student=student, section=section)
            messages.success(request, "Course added successfully.")
            return redirect("course_dashboard")

        if action == "remove":
            reg_id = request.POST.get("registration_id")
            reg = get_object_or_404(Registration, pk=reg_id, student=student)
            # record the change before deleting the registration
            tables = connection.introspection.table_names()
            if StatusHistory._meta.db_table in tables:
                reg.status_history.create(
                    status="remove",
                    author=request.user,
                )
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM registry_registration WHERE id = %s",
                    [reg_id],
                )
            messages.success(request, "Registration removed.")
            return redirect("course_dashboard")

        if action == "update":
            reg_id = request.POST.get("registration_id")
            reg = get_object_or_404(Registration, pk=reg_id, student=student)
            reg.status = request.POST.get("status")  # type: ignore[assignment]
            reg.save()
            messages.success(request, "Registration updated.")
            return redirect("course_dashboard")

    registrations = Registration.objects.filter(student=student)
    available_sections = Section.objects.exclude(
        id__in=registrations.values_list("section_id", flat=True)
    )

    context = {
        "registrations": registrations,
        "available_sections": available_sections,
        "statuses": RegistrationStatus.objects.all(),
    }

    return render(request, "website/course_dashboard.html", context)


def student_dashboard(request: HttpRequest) -> HttpResponse:  # noqa: C901
    """Render the redesigned dashboard backed with live student data."""
    student = _require_student(request.user)
    semester, open_semesters = _resolve_semester(student, request.GET.get("semester"))
    registration_open = bool(semester and semester.is_registration_open())

    def _format_semester_label() -> str:
        if semester:
            return f"{semester.academic_year.code} · Semester {semester.number}"
        if student.entry_semester:
            sem = student.entry_semester
            return f"{sem.academic_year.code} · Semester {sem.number}"
        return "Not assigned"

    def _format_schedule(section: Section) -> str:
        sessions = getattr(section, "sessions", None)
        if not sessions:
            return "Schedule TBA"
        slots: list[str] = []
        for session in sessions.all():
            schedule = session.schedule
            weekday_label = "TBA"
            if schedule and schedule.weekday is not None:
                try:
                    weekday_label = WEEKDAYS_NUMBER(schedule.weekday).label
                except ValueError:
                    weekday_label = "TBA"
            start = (
                schedule.start_time.strftime("%H:%M")
                if schedule and schedule.start_time
                else "—"
            )
            end = (
                schedule.end_time.strftime("%H:%M")
                if schedule and schedule.end_time
                else "—"
            )
            slots.append(f"{weekday_label} {start}–{end}")
        return " · ".join(slots) if slots else "Schedule TBA"

    registrations = (
        Registration.objects.filter(student=student)
        .select_related(
            "section",
            "section__semester",
            "section__curriculum_course__course",
            "section__curriculum_course__credit_hours",
            "status",
        )
        .order_by("-date_registered")
    )

    registration_total = registrations.count()
    status_summary = list(
        registrations.values("status__code", "status__label")
        .annotate(total=Count("id"))
        .order_by("status__label")
    )
    course_filters = [
        {
            "label": "All",
            "value": "all",
            "active": True,
            "count": registration_total,
        }
    ]
    for summary in status_summary:
        course_filters.append(
            {
                "label": summary["status__label"] or summary["status__code"],
                "value": summary["status__code"],
                "active": False,
                "count": summary["total"],
            }
        )

    def _section_fee(section: Section) -> Decimal:
        return getattr(section, "fee_total", Decimal("0.00"))

    course_status_rows = []
    for reg in registrations:
        section = reg.section
        course = section.curriculum_course.course
        course_status_rows.append(
            {
                "code": course.short_code or course.code,
                "title": course.title or "",
                "status": reg.status_id,
                "status_label": reg.status.label if reg.status else reg.status_id,
                "credits": section.curriculum_course.credit_hours.code,
                "semester": str(section.semester),
                "last_update": reg.date_registered.strftime("%b %d, %Y"),
                "fee": _section_fee(section),
            }
        )

    curriculum_courses_qs = (
        CurriculumCourse.objects.filter(curriculum=student.curriculum)
        .select_related("course", "credit_hours")
        .order_by("course__short_code")
    )
    curriculum_courses = list(curriculum_courses_qs)
    curriculum_course_ids = [cc.id for cc in curriculum_courses]
    course_ids = [cc.course_id for cc in curriculum_courses]

    if curriculum_course_ids:
        sections = (
            Section.objects.filter(curriculum_course_id__in=curriculum_course_ids)
            .select_related(
                "curriculum_course__course",
                "curriculum_course__credit_hours",
                "semester",
            )
            .prefetch_related("sessions__schedule")
            .annotate(
                fee_total=Coalesce(
                    Sum("sectionfee__amount"),
                    Value(
                        Decimal("0.00"),
                        output_field=DecimalField(max_digits=10, decimal_places=2),
                    ),
                )
            )
        )
        if semester:
            sections = sections.filter(semester=semester)
    else:
        sections = Section.objects.none()

    sections_by_course: dict[int, list[Section]] = defaultdict(list)
    for section in sections:
        sections_by_course[section.curriculum_course.course_id].append(section)

    passed_course_ids = set(student.passed_courses().values_list("id", flat=True))
    allowed_course_ids = set(student.allowed_courses().values_list("id", flat=True))
    prereqs = []
    if course_ids:
        prereqs = (
            Prerequisite.objects.filter(
                Q(curriculum=student.curriculum) | Q(curriculum__isnull=True),
                course_id__in=course_ids,
            )
            .select_related("prerequisite_course")
            .order_by("prerequisite_course__short_code")
        )
    prereq_map: dict[int, list[dict[str, object]]] = defaultdict(list)
    for prereq in prereqs:
        course_id = prereq.course_id
        prereq_course = prereq.prerequisite_course
        prereq_map[course_id].append(
            {
                "label": prereq_course.short_code or prereq_course.code,
                "met": prereq_course.id in passed_course_ids,
            }
        )

    available_courses: list[dict[str, object]] = []
    locked_courses: list[dict[str, object]] = []
    for cc in curriculum_courses:
        course = cc.course
        course_sections = sections_by_course.get(course.id, [])
        prereq_data = prereq_map.get(course.id, [])
        is_eligible = all(
            [
                registration_open,
                course.id in allowed_course_ids,
                bool(course_sections),
            ]
        )

        missing = [p["label"] for p in prereq_data if not p["met"]]
        reason = ""
        if not registration_open:
            reason = "Registration window is closed."
        elif missing:
            reason = f"Complete {', '.join(missing)} first."
        elif not course_sections:
            reason = "No scheduled section this semester."
        elif course.id not in allowed_course_ids:
            reason = "Already completed or blocked."

        serialized_sections = [
            {
                "id": section.id,
                "label": f"Section {section.number:02d}",
                "schedule": _format_schedule(section),
                "seats_total": section.max_seats,
                "seats_remaining": section.available_seats,
                "fee": _section_fee(section),
            }
            for section in course_sections
        ]

        course_payload = {
            "code": course.short_code or course.code,
            "title": course.title or "",
            "credits": cc.credit_hours.code,
            "elective": cc.is_elective,
            "eligible": is_eligible,
            "reason": reason,
            "prerequisites": prereq_data,
            "sections": serialized_sections,
        }
        if is_eligible:
            available_courses.append(course_payload)
        else:
            locked_courses.append(course_payload)

    completed_credits = student.completed_credits
    required_credits = (
        student.curriculum.programs.aggregate(
            total=Sum("credit_hours__code"),
        ).get("total")
        or 0
    )
    remaining_credits = max(required_credits - completed_credits, 0)
    gpa = (
        Grade.objects.filter(student=student)
        .aggregate(value=Avg("value__number"))
        .get("value")
    )

    invoices = Invoice.objects.filter(student=student)
    total_due = invoices.aggregate(total=Sum("amount_due")).get("total") or Decimal(
        "0.00"
    )
    payments = Payment.objects.filter(invoice__student=student)
    total_paid = payments.aggregate(total=Sum("amount_paid")).get("total") or Decimal(
        "0.00"
    )
    outstanding = max(total_due - total_paid, Decimal("0.00"))
    last_payment = payments.order_by("-id").select_related("invoice").first()
    if last_payment and hasattr(last_payment.invoice, "created_at"):
        last_payment_label = last_payment.invoice.created_at.strftime("%b %d, %Y")
    else:
        last_payment_label = "No payments recorded"

    currency = getattr(settings, "FINANCE_DEFAULT_CURRENCY", "USD")

    financial_summary = {
        "balance": outstanding,
        "currency": currency,
        "last_payment": last_payment_label,
    }

    credit_summary = {
        "completed": completed_credits,
        "required": required_credits,
        "remaining": remaining_credits,
        "gpa": f"{gpa:.2f}" if gpa else "N/A",
    }

    student_profile = {
        "name": student.long_name or student.user.get_full_name() or student.username,
        "student_id": student.student_id or "Pending ID",
        "academic_year": _format_semester_label(),
        "curriculum": student.curriculum.long_name or student.curriculum.short_name,
        "avatar": (
            student.photo.url if getattr(student, "photo", None) and student.photo else ""
        ),
    }

    completed_courses = []
    grades = (
        Grade.objects.filter(student=student)
        .select_related(
            "section__curriculum_course__course",
            "section__curriculum_course__credit_hours",
            "value",
        )
        .order_by("-graded_on")
    )
    for grade in grades:
        course = grade.section.curriculum_course.course
        completed_courses.append(
            {
                "code": course.short_code or course.code,
                "title": course.title or "",
                "credits": grade.section.curriculum_course.credit_hours.code,
                "grade": grade.value.code if grade.value else "",
            }
        )

    announcements: list[str] = []
    if outstanding > 0:
        announcements.append(
            f"Outstanding balance: {currency} {outstanding:.2f}. "
            "Complete payment to finalize registrations."
        )
    if semester:
        announcements.append(f"Selected semester: {semester}")
    if not registration_open:
        announcements.append("Registration window is currently closed.")
    if not announcements:
        announcements.append("You are all set for the semester.")

    curriculum_course_count = len(curriculum_courses)
    advisor_actions = [
        {
            "title": f"{student.curriculum.short_name} curriculum overview",
            "description": f"{curriculum_course_count} mapped courses in your program.",
            "cta": "#",
        },
        {
            "title": "Download unofficial transcript",
            "description": f"{len(completed_courses)} graded courses available.",
            "cta": "#",
        },
        {
            "title": "Message your advisor",
            "description": "Need clearance? Let your college advisor know.",
            "cta": "mailto:advising@tusis.edu",
        },
    ]

    registration_limits = {
        "credits_remaining": remaining_credits,
        "credits_cap": getattr(settings, "STUDENT_MAX_CREDITS", 18),
        "currency": currency,
        "balance": outstanding,
    }

    sidebar_links = [
        {"label": "Dashboard", "href": reverse("student_dashboard"), "active": True},
        {"label": "Course Registration", "href": "#courses", "active": False},
        {"label": "Financials", "href": "#records", "active": False},
        {"label": "Support", "href": "#support", "active": False},
    ]

    semester_options = [
        {
            "id": sem.id,
            "label": f"{sem.academic_year.code} · Semester {sem.number}",
            "active": semester and sem.id == semester.id,
        }
        for sem in open_semesters
    ]

    context = {
        "student_profile": student_profile,
        "sidebar_links": sidebar_links,
        "credit_summary": credit_summary,
        "financial_summary": financial_summary,
        "course_filters": course_filters,
        "course_status_rows": course_status_rows,
        "available_courses": available_courses,
        "registration_limits": registration_limits,
        "completed_courses": completed_courses,
        "advisor_actions": advisor_actions,
        "announcements": announcements,
        "current_semester": semester,
        "registration_open": registration_open,
        "semester_options": semester_options,
        "locked_courses": locked_courses,
    }

    return render(request, "website/student_dashboard.html", context)


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


def _user_group_names(user: User) -> set[str]:
    return set(user.groups.values_list("name", flat=True))


def _get_faculty_profile(user: User) -> Faculty | None:
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


def _resolve_staff_role(user: User) -> str:
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
    if "template" in config:
        template_name = config["template"]
    else:
        template_name = "website/staff/role_dashboard.html"
    return render(request, template_name, base)


@login_required
def portal_redirect(request: HttpRequest) -> HttpResponse:
    """Central landing after authentication; route users by role."""
    user = request.user
    user_groups = set(user.groups.values_list("name", flat=True))

    if user.is_superuser or user_groups.intersection(ADMIN_PORTAL_GROUPS):
        return redirect("admin:index")

    if getattr(user, "student", None):
        return redirect("student_dashboard")

    return redirect("staff_dashboard")


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


class PortalLoginView(LoginView):
    """Allow any active user to sign in, then hand off to portal redirect."""

    template_name = "website/portal_login.html"

    def get_success_url(self):
        return reverse("portal_redirect")


class PortalLogoutView(View):
    """Explicit logout that always redirects to the unified login."""

    http_method_names = ["get", "post", "head", "options"]

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        logout(request)
        return redirect("portal_login")

    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        return self.post(request, *args, **kwargs)


@permission_required("timetable.change_semester", raise_exception=True)
def registrar_course_windows(request: HttpRequest) -> HttpResponse:
    """Allow registrar staff to manage semester statuses."""
    semesters = (
        Semester.objects.select_related("academic_year", "status")
        .order_by("-academic_year__start_date", "-number")
        .all()
    )
    statuses = SemesterStatus.objects.all().order_by("code")

    if request.method == "POST":
        semester_id = request.POST.get("semester_id")
        status_code = request.POST.get("status_code")
        semester = get_object_or_404(Semester, pk=semester_id)
        if status_code not in {status.code for status in statuses}:
            messages.error(request, "Unknown status.")
            return redirect("registrar_course_windows")
        semester.status_id = status_code
        semester.save(update_fields=["status"])
        messages.success(
            request,
            f"{semester} status updated to {semester.status.label}.",
        )
        return redirect("registrar_course_windows")

    return render(
        request,
        "website/registrar_windows.html",
        {"semesters": semesters, "statuses": statuses},
    )


@permission_required("people.add_student", raise_exception=True)
def create_student(request: HttpRequest) -> HttpResponse:
    """Allow enrollment officers to create a new student profile."""
    if request.method == "POST":
        form = StudentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Student created successfully.")
            return redirect("create_student")
    else:
        form = StudentForm()

    return render(request, "website/create_student.html", {"form": form})


@permission_required("people.view_student", raise_exception=True)
def student_list(request: HttpRequest) -> HttpResponse:
    """Render a searchable list of students."""
    query = request.GET.get("q", "")
    students = Student.objects.all()
    if query:
        predicates = Q(student_id__icontains=query) | Q(username__icontains=query)
        predicates |= Q(user__first_name__icontains=query)
        predicates |= Q(user__last_name__icontains=query)
        students = students.filter(predicates)
    context = {"students": students.order_by("student_id"), "query": query}
    return render(request, "enrollment/student_list.html", context)


@permission_required("people.view_student", raise_exception=True)
def student_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Render a student profile page."""
    student = get_object_or_404(Student, pk=pk)
    return render(
        request,
        "enrollment/student_detail.html",
        {"student": student},
    )


@permission_required("people.delete_student", raise_exception=True)
def student_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Delete a student after confirmation.

    Only users in the *Enrollment Officer* group may delete a student.
    """
    if not request.user.groups.filter(name="Enrollment Officer").exists():
        raise PermissionDenied("Only officers may delete students.")

    student = get_object_or_404(Student, pk=pk)

    if request.method == "POST":
        student.delete()
        messages.success(request, "Student deleted successfully.")
        return redirect("landing")

    return render(
        request,
        "enrollment/student_confirm_delete.html",
        {"student": student},
    )
