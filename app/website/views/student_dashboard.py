"""Student dashboard view and helpers."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, DefaultDict, Iterable, Optional, TypedDict, cast

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Max, Q, Sum
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from app.academics.constants import MAX_STUDENT_CREDITS
from app.academics.models.curriculum_course import CurriCrs
from app.academics.models.prerequisite import Prerequisite
from app.finance.fee_assignment import (
    FeeAssignmentSummaryT,
    attach_sem_fee_stacks,
    optional_sem_stack_choices,
)
from app.finance.models.invoice import CrsInvoice, StdSemesterInvoice
from app.finance.models.payment import Payment
from app.people.models.student import Student
from app.registry.gpa import get_cumulative_gpa, get_grade_points_and_credits
from app.registry.models.grade import Grade
from app.registry.models.registration import Registration, RegistrationStatus
from app.timetable.choices import WEEKDAYS_NUMBER
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester
from app.timetable.utils import format_datetime, format_short_datetime

from .course_requirements import (
    ReqCheckResultT,
    build_req_context,
    eval_curri_crs_reqs,
    req_failure_msgs,
)
from .student_helpers import (
    _build_sidebar_links,
    _build_std_profile,
    _require_std,
    _resolve_sem,
)


class SemGradeRowT(TypedDict):
    """Row details for a semester grade listing."""

    code: str
    title: str
    credits: int
    grade: str


class SemGradeGpT(TypedDict):
    """Grade grouping details for a single semester."""

    semester_id: int
    label: str
    gpa: str
    credits_total: int
    receipt_url: str
    courses: list[SemGradeRowT]


def _append_reason_line(reason_lines: list[str], reason: str) -> None:
    """Append a non-empty reason line once while preserving order."""
    text = reason.strip()
    if not text or text in reason_lines:
        return
    reason_lines.append(text)


def _curri_level_hint(curriculum_course: CurriCrs) -> str:
    """Return a short curriculum placement hint for the course card UI."""
    level_number = int(curriculum_course.level_number or 0)
    if 1 <= level_number <= 10:
        return f"Level {level_number}"
    year_number = int(curriculum_course.year_number or 0)
    semester_number = int(curriculum_course.semester_number or 0)
    if 1 <= year_number <= 5 and semester_number in {1, 2}:
        return f"Y{year_number}S{semester_number}"
    return ""


@login_required
@require_POST
def download_invoice_statement(request: HttpRequest) -> HttpResponse:
    """Redirect to the invoice statement view."""
    _require_std(request.user)
    return redirect(reverse("std_invoice_statement"))


@login_required
def std_invoice_statement(request: HttpRequest) -> HttpResponse:
    """Render the invoice statement for the current student."""
    student = _require_std(request.user)
    invoices = list(
        CrsInvoice.objects.filter(student=student, balance__gt=0)
        .select_related(
            "curriculum_course__course",
            "curriculum_course__credit_hours",
            "semester__academic_year",
        )
        .order_by("semester__start_date", "curriculum_course__course__short_code")
    )
    total_due = StdSemesterInvoice.objects.filter(student=student).aggregate(
        total=Sum("balance")
    ).get("total") or Decimal("0.00")
    currency = getattr(settings, "FINANCE_DEFAULT_CURRENCY", "USD")
    statement_rows = [
        {"invoice": invoice, "created_at": format_datetime(invoice.created_at)}
        for invoice in invoices
    ]
    student_profile = _build_std_profile(student)
    sidebar_links = _build_sidebar_links("Download invoice statement", student=student)
    context = {
        "student": student,
        "statement_rows": statement_rows,
        "currency": currency,
        "total_due": total_due,
        "student_profile": student_profile,
        "sidebar_links": sidebar_links,
    }
    return render(request, "website/std_invoice_statement.html", context)


@login_required
def student_dashboard(request: HttpRequest) -> HttpResponse:  # noqa: C901
    """Render the student dashboard backed with live data.

    Args:
        request: Incoming HTTP request.

    Returns:
        Rendered student dashboard response.
    """
    student = _require_std(request.user)
    curriculum = student.primary_curriculum
    semester, open_semesters = _resolve_sem(student, request.GET.get("semester"))
    registration_open = bool(semester and semester.is_regio_open())
    registration: Optional[Registration] = None
    ajax_messages: list[dict[str, str]] = []

    def _redirect_to_sem() -> HttpResponse:
        """Redirect back to the dashboard with the current semester filter."""
        redirect_url = reverse("student_dashboard")
        selected_semester = request.POST.get("semester_id") or request.GET.get("semester")
        if selected_semester:
            redirect_url = f"{redirect_url}?semester={selected_semester}"
        return redirect(redirect_url)

    def _is_ajax_request() -> bool:
        """Return True when the request expects JSON fragments."""
        return request.headers.get("x-requested-with") == "XMLHttpRequest"

    def _push_msg(level: str, text: str) -> None:
        """Queue a message for either AJAX or full-page responses."""
        if _is_ajax_request():
            ajax_messages.append({"level": level, "text": text})
            return
        getattr(messages, level)(request, text)

    def _ensure_invoice_for_sec(section: Section) -> None:
        """Create or patch invoices so initial_amount_due is always set."""
        amount_due = section.fee_total_amount()
        invoice, created = CrsInvoice.objects.get_or_create(
            student=student,
            curriculum_course=section.curriculum_course,
            semester=section.semester,
            defaults={
                "initial_amount_due": amount_due,
                "balance": amount_due,
            },
        )
        initial_amount_due: Decimal | None = getattr(invoice, "initial_amount_due", None)
        if not created and initial_amount_due is None:
            invoice.initial_amount_due = amount_due
            if invoice.balance is None:
                invoice.balance = amount_due
            invoice.save(update_fields=["initial_amount_due", "balance", "status"])

    def _parse_sec_ids(raw_ids: str) -> list[int]:
        """Parse a comma-delimited list of section IDs into integers."""
        ids: list[int] = []
        for token in raw_ids.split(","):
            token = token.strip()
            if not token:
                continue
            try:
                ids.append(int(token))
            except ValueError:
                continue
        return ids

    def _max_credit_hours(student_obj: Student) -> int:
        """Return the per-student credit limit for the current semester."""
        return int(getattr(student_obj, "max_credit_hours", 0) or MAX_STUDENT_CREDITS)

    def _parse_optional_stack_ids(raw_ids: list[str]) -> set[int]:
        """Parse selected optional fee-stack ids from POST payload."""
        parsed_ids: set[int] = set()
        for raw_id in raw_ids:
            try:
                parsed_ids.add(int(raw_id))
            except (TypeError, ValueError):
                continue
        return parsed_ids

    def _attempt_blocked_crss(
        student_obj: Student, semester_obj: Optional[Semester]
    ) -> set[int]:
        """Return course IDs blocked by repeated registration attempts."""
        if semester_obj is None:
            return set()
        history_model = Registration.history.model
        attempt_rows = (
            history_model.objects.filter(
                student_id=student_obj.id,
                section__semester=semester_obj,
                status_id="pending",
            )
            .values("section__curriculum_course__course_id")
            .annotate(total=Count("id"))
            .filter(total__gte=2)
        )
        return {row["section__curriculum_course__course_id"] for row in attempt_rows}

    def _cooldown_crss(
        student_obj: Student,
        semester_obj: Optional[Semester],
        cutoff: datetime,
    ) -> dict[int, datetime]:
        """Return a mapping of course ids to unlock times after cancellations."""
        if semester_obj is None:
            return {}
        history_model = Registration.history.model
        canceled_rows = (
            history_model.objects.filter(
                student_id=student_obj.id,
                section__semester=semester_obj,
                status_id__in={"canceled", "removed"},
                history_date__gte=cutoff,
            )
            .values("section__curriculum_course__course_id", "history_date")
            .order_by("-history_date")
        )
        locks: dict[int, datetime] = {}
        for row in canceled_rows:
            course_id = row["section__curriculum_course__course_id"]
            history_date = row.get("history_date")
            if course_id in locks or history_date is None:
                continue
            locks[course_id] = history_date + timedelta(hours=48)
        return locks

    def _has_non_reversible_payment_history(parent_invoice_id: int) -> bool:
        """Return True when a parent invoice has cleared payment history."""
        return bool(
            Payment.history.filter(
                student_semester_invoice_id=parent_invoice_id,
                status_id="cleared",
            ).exists()
        )

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "register":
            raw_ids = request.POST.get("section_ids", "")
            section_ids = _parse_sec_ids(raw_ids)
            optional_stack_ids = _parse_optional_stack_ids(
                request.POST.getlist("optional_fee_stack_ids")
            )
            if not section_ids:
                if _is_ajax_request():
                    return JsonResponse(
                        {
                            "ok": False,
                            "message": "Select at least one section to register.",
                        },
                        status=400,
                    )
                messages.warning(request, "Select at least one section to register.")
                return _redirect_to_sem()
            if not semester or not registration_open:
                if _is_ajax_request():
                    return JsonResponse(
                        {
                            "ok": False,
                            "message": "Registration is not open for this semester.",
                        },
                        status=400,
                    )
                messages.error(request, "Registration is not open for this semester.")
                return _redirect_to_sem()
            # Pending registrations are cleaned up after 48 hours by a scheduled task.
            pending_status = RegistrationStatus.get_dft()
            current_registrations_qs = Registration.objects.filter(
                student=student,
                section__semester=semester,
            ).exclude(status_id__in={"canceled", "removed"})
            current_course_ids = set(
                current_registrations_qs.values_list(
                    "section__curriculum_course__course_id",
                    flat=True,
                )
            )
            current_credits = (
                current_registrations_qs.aggregate(
                    total=Sum("section__curriculum_course__credit_hours_id")
                ).get("total")
                or 0
            )
            allowed_course_ids = set(student.allowed_crss().values_list("id", flat=True))
            sections = (
                Section.objects.filter(id__in=section_ids, semester=semester)
                .select_related("curriculum_course__course")
                .prefetch_related(
                    "curriculum_course__requirement_groups__members__required_course"
                )
                .order_by("id")
            )
            existing_regs = Registration.objects.filter(
                student=student,
                section__semester=semester,
                section_id__in=section_ids,
            ).select_related("status")
            existing_by_section = {reg.section_id: reg for reg in existing_regs}
            new_credit_total = 0
            selected_course_ids: set[int] = set()
            selected_curriculum_course_by_course_id: dict[int, CurriCrs] = {}
            for section in sections:
                existing = existing_by_section.get(section.id)
                if existing and existing.status_id not in {"canceled", "removed"}:
                    continue
                course_id = section.curriculum_course.course_id
                if course_id in current_course_ids or course_id in selected_course_ids:
                    continue
                selected_course_ids.add(course_id)
                selected_curriculum_course_by_course_id[course_id] = (
                    section.curriculum_course
                )
                new_credit_total += int(section.curriculum_course.credit_hours.code)
            requirement_context = build_req_context(student)
            blocked_by_requirements: dict[int, ReqCheckResultT] = {}
            requirement_errors_by_course: dict[int, str] = {}
            for (
                course_id,
                curriculum_course,
            ) in selected_curriculum_course_by_course_id.items():
                requirement_result = eval_curri_crs_reqs(
                    student=student,
                    curriculum_course=curriculum_course,
                    selected_course_ids=selected_course_ids,
                    context=requirement_context,
                )
                if requirement_result["ok"]:
                    continue
                blocked_by_requirements[course_id] = requirement_result
                course_label = (
                    curriculum_course.course.short_code or curriculum_course.course.code
                )
                reason_text = "; ".join(req_failure_msgs(requirement_result["failures"]))
                requirement_errors_by_course[course_id] = f"{course_label}: {reason_text}"
            max_credit_hours = _max_credit_hours(student)
            # Enforce the per-student credit limit before persisting registrations.
            if current_credits + new_credit_total > max_credit_hours:
                msg = (
                    "Selected sections exceed the credit limit for this semester. "
                    "Reduce your selection or ask a staff member to adjust your limit."
                )
                if _is_ajax_request():
                    return JsonResponse({"ok": False, "message": msg}, status=400)
                messages.error(request, msg)
                return _redirect_to_sem()
            created = 0
            updated = 0
            skipped = 0
            cooldown_skipped = 0
            attempts_blocked = 0
            duplicate_course_skipped = 0
            requirement_blocked = 0
            cooldown_cutoff = timezone.now() - timedelta(hours=48)
            blocked_courses = _attempt_blocked_crss(student, semester)
            cooldown_course_locks_for_register = _cooldown_crss(
                student,
                semester,
                cooldown_cutoff,
            )
            cooldown_courses = set(cooldown_course_locks_for_register)
            selection_course_ids: set[int] = set()
            fee_assignment_summary: FeeAssignmentSummaryT = {
                "added": 0,
                "removed_optional": 0,
                "ignored_optional": 0,
            }
            with transaction.atomic():
                for section in sections:
                    if section.curriculum_course.course_id not in allowed_course_ids:
                        skipped += 1
                        continue
                    # > We should not need this as a student cannot select a blocked course, nor cooldown_course
                    if section.curriculum_course.course_id in blocked_courses:
                        attempts_blocked += 1
                        continue
                    if section.curriculum_course.course_id in cooldown_courses:
                        cooldown_skipped += 1
                        continue
                    course_id = section.curriculum_course.course_id
                    if (
                        course_id in current_course_ids
                        or course_id in selection_course_ids
                    ):
                        duplicate_course_skipped += 1
                        continue
                    if course_id in blocked_by_requirements:
                        requirement_blocked += 1
                        continue
                    selection_course_ids.add(course_id)
                    registration, was_created = Registration.objects.get_or_create(
                        student=student,
                        section=section,
                        defaults={"status": pending_status},
                    )
                    if was_created:
                        created += 1
                        current_course_ids.add(course_id)
                        _ensure_invoice_for_sec(section)
                        continue
                    if registration.status_id in {"canceled", "removed"}:
                        registration.status = pending_status
                        registration.save(update_fields=["status"])
                        updated += 1
                        current_course_ids.add(course_id)
                        _ensure_invoice_for_sec(section)
                    else:
                        skipped += 1
                if semester is not None:
                    fee_assignment_summary = attach_sem_fee_stacks(
                        student=student,
                        semester=semester,
                        optional_stack_ids=optional_stack_ids,
                    )
            if created or updated:
                _push_msg(
                    "success",
                    f"Saved {created + updated} registration(s).",
                )
            if fee_assignment_summary["ignored_optional"]:
                _push_msg(
                    "warning",
                    (
                        "Some optional fee selections were ignored because they are "
                        "not configured for student self-service."
                    ),
                )
            if duplicate_course_skipped:
                _push_msg(
                    "warning",
                    (
                        "Skipped "
                        f"{duplicate_course_skipped} selection(s) because the course "
                        "is already registered this semester."
                    ),
                )
            if skipped:
                _push_msg(
                    "info",
                    f"Skipped {skipped} section(s) already registered or unavailable.",
                )
            if cooldown_skipped:
                _push_msg(
                    "warning",
                    f"{cooldown_skipped} section(s) are locked for 48 hours after "
                    "cancelation.",
                )
            if attempts_blocked:
                _push_msg(
                    "error",
                    f"{attempts_blocked} section(s) hit the two-attempt limit for this "
                    "semester.",
                )
            if requirement_blocked:
                for message in requirement_errors_by_course.values():
                    _push_msg("error", message)
                if _is_ajax_request() and not (created or updated):
                    return JsonResponse(
                        {
                            "ok": False,
                            "message": " ".join(requirement_errors_by_course.values()),
                        },
                        status=400,
                    )
            if not _is_ajax_request():
                return _redirect_to_sem()
        if action == "cancel_registration":
            reg_id = request.POST.get("registration_id")
            if not reg_id:
                if _is_ajax_request():
                    return JsonResponse(
                        {"ok": False, "message": "Select a registration to cancel."},
                        status=400,
                    )
                messages.error(request, "Select a registration to cancel.")
                return _redirect_to_sem()
            registration = Registration.objects.filter(pk=reg_id, student=student).first()
            if not registration:
                if _is_ajax_request():
                    return JsonResponse(
                        {"ok": False, "message": "Registration not found."},
                        status=404,
                    )
                messages.error(request, "Registration not found.")
                return _redirect_to_sem()
            if registration.status_id != "pending":
                if _is_ajax_request():
                    return JsonResponse(
                        {
                            "ok": False,
                            "message": "Only pending registrations can be canceled.",
                        },
                        status=400,
                    )
                messages.warning(
                    request,
                    "Only pending registrations can be canceled.",
                )
                return _redirect_to_sem()
            canceled_status = RegistrationStatus.objects.filter(code="canceled").first()
            if canceled_status is None:
                if _is_ajax_request():
                    return JsonResponse(
                        {"ok": False, "message": "Canceled status is not configured."},
                        status=500,
                    )
                messages.error(request, "Canceled status is not configured.")
                return _redirect_to_sem()
            invoice_qs = CrsInvoice.objects.filter(
                student=student,
                curriculum_course=registration.section.curriculum_course,
                semester=registration.section.semester,
            )
            parent_invoice_ids = list(
                invoice_qs.values_list("student_semester_invoice_id", flat=True)
            )
            parent_invoice_ids = [value for value in parent_invoice_ids if value]
            payments_qs = Payment.objects.filter(
                student_semester_invoice_id__in=parent_invoice_ids
            )
            if payments_qs.exclude(status_id="pending").exists():
                if _is_ajax_request():
                    return JsonResponse(
                        {
                            "ok": False,
                            "message": "This registration has cleared payments.",
                        },
                        status=400,
                    )
                messages.error(
                    request,
                    "This registration has cleared payments and cannot be canceled.",
                )
                return _redirect_to_sem()
            with transaction.atomic():
                registration.status = canceled_status
                registration.save(update_fields=["status"])
                if parent_invoice_ids:
                    invoice_qs.delete()
                    for parent_invoice in StdSemesterInvoice.objects.filter(
                        id__in=parent_invoice_ids
                    ):
                        has_semester_fees = parent_invoice.fee_stacks.exists()
                        has_non_reversible_history = _has_non_reversible_payment_history(
                            parent_invoice.id
                        )
                        if (
                            parent_invoice.course_invoices.exists()
                            or has_semester_fees
                            or has_non_reversible_history
                        ):
                            parent_invoice.refresh_totals_from_sources(save_model=True)
                            continue
                        Payment.objects.filter(
                            student_semester_invoice=parent_invoice,
                            status_id="pending",
                        ).delete()
                        if parent_invoice.payments.exists():
                            # Keep SSI when non-pending payments are still present.
                            parent_invoice.refresh_totals_from_sources(save_model=True)
                            continue
                        parent_invoice.delete()
            _push_msg("success", "Registration canceled.")
            if not _is_ajax_request():
                return _redirect_to_sem()

    def _format_sem_label() -> str:
        """Return a display label for the selected semester."""
        if semester:
            return f"{semester.academic_year.code} · Semester {semester.number}"
        if student.entry_semester:
            sem = student.entry_semester
            return f"{sem.academic_year.code} · Semester {sem.number}"
        return "Not assigned"

    def _format_schedule(section: Section) -> str:
        """Return a formatted schedule string for a section."""
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

    active_registrations = registrations.exclude(status_id__in={"canceled", "removed"})
    history_model = Registration.history.model
    history_rows = (
        history_model.objects.filter(id__in=registrations.values_list("id", flat=True))
        .values("id")
        .annotate(last_change=Max("history_date"))
    )
    history_dates = {row["id"]: row["last_change"] for row in history_rows}

    invoices = CrsInvoice.objects.filter(student=student)
    invoice_key_rows = list(
        invoices.values_list(
            "curriculum_course_id",
            "semester_id",
            "id",
            "student_semester_invoice_id",
        )
    )
    invoice_keys = {(row[0], row[1]) for row in invoice_key_rows}
    invoice_id_by_key = {(row[0], row[1]): row[2] for row in invoice_key_rows}
    parent_invoice_id_by_invoice_id = {
        row[2]: row[3]
        for row in invoice_key_rows
        if row[2] is not None and row[3] is not None
    }
    payment_last_updates: dict[int, datetime] = {}
    parent_invoice_ids = [row[3] for row in invoice_key_rows if row[3] is not None]
    if parent_invoice_ids:
        payment_history_rows = (
            Payment.history.filter(student_semester_invoice_id__in=parent_invoice_ids)
            .values("student_semester_invoice_id")
            .annotate(last_change=Max("history_date"))
        )
        payment_last_updates = {
            row["student_semester_invoice_id"]: row["last_change"]
            for row in payment_history_rows
            if row["last_change"]
        }

    course_status_rows = []
    course_status_total_credits = 0
    for reg in registrations:
        if reg.status_id == "canceled":
            continue
        section = reg.section
        course = section.curriculum_course.course
        last_change = history_dates.get(reg.id) or reg.date_registered
        credits = int(section.curriculum_course.credit_hours.code)
        course_status_total_credits += credits
        is_cleared = reg.status_id == "cleared"
        is_approved = reg.status_id == "approved"
        can_view = is_cleared or is_approved
        invoice_id = invoice_id_by_key.get(
            (section.curriculum_course_id, section.semester_id)
        )
        parent_invoice_id = (
            parent_invoice_id_by_invoice_id.get(invoice_id) if invoice_id else None
        )
        payment_last_update = (
            format_datetime(payment_last_updates[parent_invoice_id])
            if parent_invoice_id and parent_invoice_id in payment_last_updates
            else "-"
        )
        course_status_rows.append(
            {
                "code": course.short_code or course.code,
                "title": course.title or "",
                "status": reg.status_id,
                "status_label": reg.status.label if reg.status else reg.status_id,
                "credits": credits,
                "semester": str(section.semester),
                "last_update": last_change.strftime("%b %d, %Y %H:%M"),
                "payment_last_update": payment_last_update,
                "fee": section.fee_total_amount(),
                "registration_id": reg.id,
                "can_cancel": reg.status_id == "pending",
                "can_view": can_view,
                "section_url": (
                    reverse("std_sec_detail", args=[section.id]) if can_view else ""
                ),
            }
        )

    curriculum_courses_qs = (
        CurriCrs.objects.filter(curriculum=curriculum)
        .select_related("course", "credit_hours")
        .prefetch_related("requirement_groups__members__required_course")
        .order_by("course__short_code")
    )
    curriculum_courses = list(curriculum_courses_qs)
    curriculum_course_ids = [cc.id for cc in curriculum_courses]
    course_ids = [cc.course_id for cc in curriculum_courses]

    if curriculum_course_ids:
        sections_qs: Any = Section.objects.filter(
            curriculum_course_id__in=curriculum_course_ids
        )
        sections_qs = sections_qs.select_related(
            "curriculum_course__course",
            "curriculum_course__credit_hours",
            "semester",
        )
        sections_qs = sections_qs.prefetch_related("sessions__schedule")
        if semester:
            sections_qs = sections_qs.filter(semester=semester)
        sections = sections_qs
    else:
        sections = Section.objects.none()

    sections_by_course: dict[int, list[Section]] = defaultdict(list)
    for section in sections:
        sections_by_course[section.curriculum_course.course_id].append(section)

    registered_course_ids: set[int] = set()
    pending_course_ids: set[int] = set()
    cooldown_course_locks: dict[int, datetime] = {}
    cooldown_course_ids: set[int] = set()
    attempt_blocked_course_ids: set[int] = set()
    registered_status_by_course: dict[int, str] = {}
    registered_status_id_by_course: dict[int, str] = {}
    if semester:
        semester_registrations = active_registrations.filter(section__semester=semester)
        registered_course_ids = set(
            semester_registrations.values_list(
                "section__curriculum_course__course_id",
                flat=True,
            )
        )
        for reg in semester_registrations:
            course_id = reg.section.curriculum_course.course_id
            if course_id not in registered_status_by_course:
                status_id = reg.status_id or ""
                registered_status_id_by_course[course_id] = status_id
                registered_status_by_course[course_id] = (
                    reg.status.label if reg.status else status_id
                )
            if reg.status_id == "pending":
                pending_course_ids.add(course_id)
        cooldown_course_locks = _cooldown_crss(
            student,
            semester,
            timezone.now() - timedelta(hours=48),
        )
        cooldown_course_ids = set(cooldown_course_locks)
        attempt_blocked_course_ids = _attempt_blocked_crss(student, semester)

    requirement_context = build_req_context(student)
    passed_course_ids = requirement_context["passed_course_ids"]
    allowed_course_ids = set(student.allowed_crss().values_list("id", flat=True))
    prereqs: Iterable[Prerequisite] = []
    if course_ids:
        prereqs = (
            Prerequisite.objects.filter(
                Q(curriculum=curriculum) | Q(curriculum__isnull=True),
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
    registered_courses: list[dict[str, object]] = []
    locked_courses: list[dict[str, object]] = []
    # Keep a dedicated list for canceled courses to drive the gray area UI.
    canceled_courses: list[dict[str, object]] = []
    for cc in curriculum_courses:
        course = cc.course
        course_sections = sections_by_course.get(course.id, [])
        has_scheduled_section = bool(course_sections)
        prereq_data = prereq_map.get(course.id, [])
        requirement_result = eval_curri_crs_reqs(
            student=student,
            curriculum_course=cc,
            selected_course_ids={course.id},
            context=requirement_context,
        )
        requirement_failures = requirement_result["failures"]
        blocking_failures = [
            failure
            for failure in requirement_failures
            if failure.get("code") != "incomplete_coreq_all"
        ]
        requirement_reason_lines = req_failure_msgs(requirement_failures)
        is_eligible = all(
            [
                registration_open,
                course.id in allowed_course_ids,
                course.id not in registered_course_ids,
                course.id not in cooldown_course_ids,
                course.id not in attempt_blocked_course_ids,
                not blocking_failures,
                has_scheduled_section,
            ]
        )

        missing = [cast(str, p["label"]) for p in prereq_data if not p["met"]]
        reason_lines: list[str] = []
        if course.id in attempt_blocked_course_ids:
            _append_reason_line(
                reason_lines, "Registration limit reached for this semester."
            )
        elif course.id in cooldown_course_ids:
            pass
        elif course.id in registered_course_ids:
            pass
        else:
            if not registration_open:
                _append_reason_line(reason_lines, "Registration window is closed.")
            if missing:
                _append_reason_line(reason_lines, f"Complete {', '.join(missing)} first.")
            for requirement_line in requirement_reason_lines:
                _append_reason_line(reason_lines, requirement_line)
            if not has_scheduled_section:
                _append_reason_line(reason_lines, "No scheduled section this semester.")
            if course.id not in allowed_course_ids:
                _append_reason_line(reason_lines, "Already completed or blocked.")

        reason = reason_lines[0] if reason_lines else ""

        serialized_sections = [
            {
                "id": section.id,
                "label": f"Section {section.number:02d}",
                "schedule": _format_schedule(section),
                "seats_total": section.max_seats,
                "seats_remaining": section.available_seats,
                "fee": section.fee_total_amount(),
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
            "reason_lines": reason_lines,
            "prerequisites": prereq_data,
            "sections": serialized_sections,
            "level_hint": _curri_level_hint(cc),
            "status_label": "",
            "status_class": "bg-secondary",
            "locked_until": "",
        }
        status_id = registered_status_id_by_course.get(course.id, "")
        if course.id in pending_course_ids:
            course_payload["status_label"] = registered_status_by_course.get(
                course.id, "Pending"
            )
            course_payload["status_class"] = "bg-info-subtle text-info"
            # Pending courses are visible in the status table; keep them out of
            # the gray area list as requested.
            continue
        elif course.id in registered_course_ids:
            if status_id in {"cleared", "approved"}:
                continue
            course_payload["status_label"] = registered_status_by_course.get(
                course.id, "Registered"
            )
            # Active registrations are covered elsewhere; do not show here.
            continue
        elif course.id in cooldown_course_ids:
            unlock_time = cooldown_course_locks.get(course.id)
            if unlock_time:
                course_payload["status_label"] = (
                    f"Canceled until {format_short_datetime(unlock_time)}"
                )
            else:
                course_payload["status_label"] = "Canceled for semester"
            course_payload["status_class"] = "bg-secondary text-white"
            canceled_courses.append(course_payload)
        elif is_eligible:
            available_courses.append(course_payload)
        else:
            # Informational bucket: all non-selectable curriculum courses stay visible.
            locked_courses.append(course_payload)

    gpa_result = get_cumulative_gpa(student=student, curriculum=curriculum)
    gpa = gpa_result["gpa"]

    total_due = StdSemesterInvoice.objects.filter(student=student).aggregate(
        total=Sum("balance")
    ).get("total") or Decimal("0.00")
    payments = Payment.objects.filter(student_semester_invoice__student=student)
    # Receipt availability is driven by any recorded payment amount.
    cleared_invoice_semester_ids = set(
        payments.filter(amount_paid__gt=0).values_list(
            "student_semester_invoice__semester_id",
            flat=True,
        )
    )
    # balance already reflects the remaining balance after cleared payments.
    pending_registrations = active_registrations.filter(
        status_id="pending"
    ).select_related(
        "section__curriculum_course__course",
        "section__curriculum_course__credit_hours",
    )
    pending_registrations_list = list(pending_registrations)
    pending_total = sum(
        (
            reg.section.fee_total_amount()
            for reg in pending_registrations_list
            if (
                reg.section.curriculum_course_id,
                reg.section.semester_id,
            )
            not in invoice_keys
        ),
        Decimal("0.00"),
    )
    has_pending_registrations = bool(pending_registrations_list)
    outstanding = total_due + pending_total
    last_payment = (
        payments.order_by("-id").select_related("student_semester_invoice").first()
    )
    if last_payment and hasattr(last_payment.student_semester_invoice, "created_at"):
        last_payment_label = last_payment.student_semester_invoice.created_at.strftime(
            "%b %d, %Y"
        )
    else:
        last_payment_label = "No payments recorded"

    currency = getattr(settings, "FINANCE_DEFAULT_CURRENCY", "USD")

    financial_summary = {
        "balance": outstanding,
        "currency": currency,
        "last_payment": last_payment_label,
    }

    student_profile = _build_std_profile(student)
    student_profile["academic_year"] = _format_sem_label()

    completed_courses: list[SemGradeRowT] = []
    semester_grade_groups: list[SemGradeGpT] = []
    semester_grade_lookup: dict[int, SemGradeGpT] = {}
    semester_gpa_points: DefaultDict[int, float] = defaultdict(float)
    semester_gpa_credits: DefaultDict[int, int] = defaultdict(int)
    # Track total credits per semester for display.
    semester_credit_totals: DefaultDict[int, int] = defaultdict(int)
    semester_sort_info: dict[int, tuple[date, int]] = {}
    validated_credits_total = 0
    grades = (
        Grade.objects.filter(student=student)
        .select_related(
            "section__curriculum_course__course",
            "section__curriculum_course__credit_hours",
            "section__semester",
            "section__semester__academic_year",
            "value",
        )
        .order_by(
            "-section__semester__start_date",
            "-section__semester__number",
            "-graded_on",
        )
    )
    # > Group completed grades by semester with GPA summaries.
    for grade in grades:
        section = grade.section
        semester_obj = section.semester
        semester_id = semester_obj.id
        if semester_id not in semester_sort_info:
            semester_sort_info[semester_id] = (
                semester_obj.start_date
                or semester_obj.academic_year.start_date
                or date.min,
                semester_obj.number,
            )
        group = semester_grade_lookup.get(semester_id)
        if group is None:
            group = {
                "semester_id": semester_id,
                "label": (
                    f"{semester_obj.academic_year.code} · Semester {semester_obj.number}"
                ),
                "gpa": "N/A",
                "credits_total": 0,
                "receipt_url": "",
                "courses": [],
            }
            semester_grade_lookup[semester_id] = group
            semester_grade_groups.append(group)

        course = section.curriculum_course.course
        credits = int(section.curriculum_course.credit_hours.code)
        grade_value = grade.value
        grade_code = grade_value.code.upper() if grade_value and grade_value.code else ""

        row: SemGradeRowT = {
            "code": course.short_code or course.code,
            "title": course.title or "",
            "credits": credits,
            "grade": grade_code,
        }
        group["courses"].append(row)
        completed_courses.append(row)
        semester_credit_totals[semester_id] += credits

        if not grade_value or grade_value.number is None:
            continue
        if grade_value.number >= 1:
            validated_credits_total += credits
        gpa_values = get_grade_points_and_credits(grade)
        if gpa_values is not None:
            quality_points, gpa_credits = gpa_values
            semester_gpa_points[semester_id] += quality_points
            semester_gpa_credits[semester_id] += gpa_credits

    for group in semester_grade_groups:
        semester_id = group["semester_id"]
        credit_total = semester_gpa_credits.get(semester_id, 0)
        if credit_total:
            gpa_value = semester_gpa_points[semester_id] / credit_total
            group["gpa"] = f"{gpa_value:.2f}"
        group["credits_total"] = semester_credit_totals.get(semester_id, 0)

    semester_grade_groups.sort(
        key=lambda group: semester_sort_info.get(group["semester_id"], (date.min, 0)),
        reverse=True,
    )
    for group in semester_grade_groups:
        if group["semester_id"] in cleared_invoice_semester_ids:
            group["receipt_url"] = reverse(
                "std_payment_receipt",
                args=[group["semester_id"]],
            )
        group["courses"].sort(key=lambda row: row["code"] or "")

    credit_summary = {
        "gpa": f"{gpa:.2f}" if gpa else "N/A",
        "validated": validated_credits_total,
    }

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
    announcements.append(
        "Canceled registrations lock sections for 48 hours; after two attempts, "
        "the course is locked for the semester."
    )

    curriculum_course_count = len(curriculum_courses)
    advisor_actions = [
        {
            "title": f"{curriculum.short_name} curriculum overview",
            "description": f"{curriculum_course_count} mapped courses in your program.",
            "cta": reverse("std_curri_crss"),
        },
        # Unofficial transcript card removed for the current dashboard scope.
        {
            "title": "Message your advisor",
            "description": "Need clearance? Let your college advisor know.",
            "cta": "mailto:advising@tusis.edu",
        },
    ]

    current_semester_credits = 0
    if semester:
        current_semester_credits = (
            active_registrations.filter(section__semester=semester)
            .aggregate(total=Sum("section__curriculum_course__credit_hours_id"))
            .get("total")
            or 0
        )

    credits_max = _max_credit_hours(student)
    credits_remaining = max(credits_max - current_semester_credits, 0)
    registration_limits = {
        "credits_selected": current_semester_credits,
        "credits_max": credits_max,
        "credits_remaining": credits_remaining,
        "currency": currency,
        "balance": outstanding,
    }
    current_semester_receipt_url = ""
    if semester and semester.id in cleared_invoice_semester_ids:
        current_semester_receipt_url = reverse(
            "std_payment_receipt",
            args=[semester.id],
        )

    sidebar_links = _build_sidebar_links("Dashboard", student=student)

    semester_options = [
        {
            "id": sem.id,
            "label": f"{sem.academic_year.code} · Semester {sem.number}",
            "active": semester and sem.id == semester.id,
        }
        for sem in open_semesters
    ]
    optional_fee_stack_options = (
        optional_sem_stack_choices(student=student, semester=semester)
        if semester is not None
        else []
    )

    context = {
        "student_profile": student_profile,
        "sidebar_links": sidebar_links,
        "credit_summary": credit_summary,
        "financial_summary": financial_summary,
        "course_status_rows": course_status_rows,
        "course_status_total_credits": course_status_total_credits,
        "current_semester_receipt_url": current_semester_receipt_url,
        "available_courses": available_courses,
        "registered_courses": registered_courses,
        "canceled_courses": canceled_courses,
        "registration_limits": registration_limits,
        "completed_courses": completed_courses,
        "semester_grade_groups": semester_grade_groups,
        "advisor_actions": advisor_actions,
        "announcements": announcements,
        "current_semester": semester,
        "registration_open": registration_open,
        "semester_options": semester_options,
        "optional_fee_stack_options": optional_fee_stack_options,
        "locked_courses": locked_courses,
        "has_pending_registrations": has_pending_registrations,
    }

    if _is_ajax_request() and request.method == "POST":
        registration_limits_payload = {
            "credits_selected": registration_limits.get("credits_selected", 0),
            "credits_max": registration_limits.get("credits_max", 0),
        }
        fragments = {
            "course_table": render_to_string(
                "website/partials/student_dashboard_course_table.html",
                context,
                request=request,
            ),
            "course_list": render_to_string(
                "website/partials/student_dashboard_course_list.html",
                context,
                request=request,
            ),
        }
        return JsonResponse(
            {
                "ok": True,
                "fragments": fragments,
                "messages": ajax_messages,
                "registration_limits": registration_limits_payload,
            }
        )

    return render(request, "website/student_dashboard.html", context)
