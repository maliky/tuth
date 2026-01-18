"""Student dashboard view and helpers."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, DefaultDict, Iterable, Optional, TypedDict, cast

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Avg, Count, DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from app.academics.models.course import CurriculumCourse
from app.academics.models.prerequisite import Prerequisite
from app.finance.models.invoice import Invoice
from app.finance.models.payment import Payment
from app.people.models.student import Student
from app.registry.models.grade import Grade
from app.finance.utils import tuition_for
from app.registry.models.registration import Registration, RegistrationStatus
from app.timetable.choices import WEEKDAYS_NUMBER
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester

from .student_helpers import _require_student, _resolve_semester


GPA_EXCLUDED_CODES = {"ip", "ng", "w", "i", "ab", "dr"}


class SemesterGradeRowT(TypedDict):
    """Row details for a semester grade listing."""

    code: str
    title: str
    credits: int
    grade: str


class SemesterGradeGroupT(TypedDict):
    """Grade grouping details for a single semester."""

    semester_id: int
    label: str
    gpa: str
    credits_total: int
    courses: list[SemesterGradeRowT]


@login_required
def student_dashboard(request: HttpRequest) -> HttpResponse:  # noqa: C901
    """Render the student dashboard backed with live data.

    Args:
        request: Incoming HTTP request.

    Returns:
        Rendered student dashboard response.
    """
    student = _require_student(request.user)
    semester, open_semesters = _resolve_semester(student, request.GET.get("semester"))
    registration_open = bool(semester and semester.is_registration_open())
    registration: Optional[Registration] = None

    def _redirect_to_semester() -> HttpResponse:
        """Redirect back to the dashboard with the current semester filter."""
        redirect_url = reverse("student_dashboard")
        selected_semester = request.POST.get("semester_id") or request.GET.get("semester")
        if selected_semester:
            redirect_url = f"{redirect_url}?semester={selected_semester}"
        return redirect(redirect_url)

    def _parse_section_ids(raw_ids: str) -> list[int]:
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

    def _attempt_blocked_courses(
        student_obj: Student, semester_obj: Optional[Semester]
    ) -> set[int]:
        """Return course IDs blocked by repeated reservation attempts."""
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

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "reserve":
            raw_ids = request.POST.get("section_ids", "")
            section_ids = _parse_section_ids(raw_ids)
            if not section_ids:
                messages.warning(request, "Select at least one section to reserve.")
                return _redirect_to_semester()
            if not semester or not registration_open:
                messages.error(request, "Reservation is not open for this semester.")
                return _redirect_to_semester()
            # Pending reservations are cleaned up after 48 hours by a scheduled task.
            pending_status = RegistrationStatus.get_default()
            allowed_course_ids = set(
                student.allowed_courses().values_list("id", flat=True)
            )
            sections = (
                Section.objects.filter(id__in=section_ids, semester=semester)
                .select_related("curriculum_course__course")
                .order_by("id")
            )
            created = 0
            updated = 0
            skipped = 0
            cooldown_skipped = 0
            attempts_blocked = 0
            cooldown_cutoff = timezone.now() - timedelta(hours=48)
            blocked_courses = _attempt_blocked_courses(student, semester)
            cooldown_courses = set(
                Registration.objects.filter(
                    student=student,
                    status_id__in={"canceled", "removed"},
                    section__semester=semester,
                    date_registered__gte=cooldown_cutoff,
                ).values_list("section__curriculum_course__course_id", flat=True)
            )
            with transaction.atomic():
                for section in sections:
                    if section.curriculum_course.course_id not in allowed_course_ids:
                        skipped += 1
                        continue
                    if section.curriculum_course.course_id in blocked_courses:
                        attempts_blocked += 1
                        continue
                    if section.curriculum_course.course_id in cooldown_courses:
                        cooldown_skipped += 1
                        continue
                    registration, was_created = Registration.objects.get_or_create(
                        student=student,
                        section=section,
                        defaults={"status": pending_status},
                    )
                    if was_created:
                        created += 1
                        continue
                    if registration.status_id in {"canceled", "removed"}:
                        registration.status = pending_status
                        registration.date_registered = timezone.now()
                        registration.save(update_fields=["status", "date_registered"])
                        updated += 1
                    else:
                        skipped += 1
            if created or updated:
                messages.success(
                    request,
                    f"Saved {created + updated} reservation(s).",
                )
            if skipped:
                messages.info(
                    request,
                    f"Skipped {skipped} section(s) already reserved or unavailable.",
                )
            if cooldown_skipped:
                messages.warning(
                    request,
                    f"{cooldown_skipped} section(s) are locked for 48 hours after "
                    "cancelation.",
                )
            if attempts_blocked:
                messages.error(
                    request,
                    f"{attempts_blocked} section(s) hit the two-attempt limit for this "
                    "semester.",
                )
            return _redirect_to_semester()
        if action == "cancel_reservation":
            reg_id = request.POST.get("registration_id")
            if not reg_id:
                messages.error(request, "Select a reservation to cancel.")
                return _redirect_to_semester()
            registration = Registration.objects.filter(pk=reg_id, student=student).first()
            if not registration:
                messages.error(request, "Reservation not found.")
                return _redirect_to_semester()
            if registration.status_id != "pending":
                messages.warning(
                    request,
                    "Only pending reservations can be canceled.",
                )
                return _redirect_to_semester()
            canceled_status = RegistrationStatus.objects.filter(code="canceled").first()
            if canceled_status is None:
                messages.error(request, "Canceled status is not configured.")
                return _redirect_to_semester()
            registration.status = canceled_status
            # Reuse date_registered as a lock timestamp for cooldown enforcement.
            registration.date_registered = timezone.now()
            registration.save(update_fields=["status", "date_registered"])
            messages.success(request, "Reservation canceled.")
            return _redirect_to_semester()

    def _format_semester_label() -> str:
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
        .prefetch_related("section__sectionfee_set")
        .order_by("-date_registered")
    )

    active_registrations = registrations.exclude(status_id__in={"canceled", "removed"})
    registration_total = active_registrations.count()
    summary_lookup: dict[str, dict[str, Any]] = {}
    for reg in active_registrations:
        code = reg.status.code if reg.status else reg.status_id
        label = reg.status.label if reg.status else reg.status_id
        entry = summary_lookup.setdefault(
            code,
            {"status__code": code, "status__label": label, "total": 0},
        )
        entry["total"] += 1
    status_summary: list[dict[str, Any]] = sorted(
        summary_lookup.values(), key=lambda item: item["status__label"] or ""
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
        """Return the total fee for a section, including tuition."""
        # Include baseline tuition even when no SectionFee rows exist.
        base_fee = getattr(section, "fee_total", None)
        if base_fee is None:
            fee_set = getattr(section, "sectionfee_set", None)
            if fee_set is not None:
                base_fee = sum(
                    (fee.amount for fee in fee_set.all()),
                    Decimal("0.00"),
                )
            else:
                base_fee = Decimal("0.00")
        return base_fee + tuition_for(section.curriculum_course)

    course_status_rows = []
    for reg in active_registrations:
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
                "registration_id": reg.id,
                "can_cancel": reg.status_id == "pending",
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
        sections_qs: Any = Section.objects.filter(
            curriculum_course_id__in=curriculum_course_ids
        )
        sections_qs = sections_qs.select_related(
            "curriculum_course__course",
            "curriculum_course__credit_hours",
            "semester",
        )
        sections_qs = sections_qs.prefetch_related("sessions__schedule")
        sections_qs = sections_qs.annotate(
            fee_total=Coalesce(
                Sum("sectionfee__amount"),
                Value(
                    Decimal("0.00"),
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                ),
            )
        )
        if semester:
            sections_qs = sections_qs.filter(semester=semester)
        sections = sections_qs
    else:
        sections = Section.objects.none()

    sections_by_course: dict[int, list[Section]] = defaultdict(list)
    for section in sections:
        sections_by_course[section.curriculum_course.course_id].append(section)

    registered_course_ids: set[int] = set()
    cooldown_course_ids: set[int] = set()
    attempt_blocked_course_ids: set[int] = set()
    if semester:
        registered_course_ids = set(
            active_registrations.filter(section__semester=semester).values_list(
                "section__curriculum_course__course_id",
                flat=True,
            )
        )
        cooldown_course_ids = set(
            registrations.filter(
                section__semester=semester,
                status_id__in={"canceled", "removed"},
                date_registered__gte=timezone.now() - timedelta(hours=48),
            ).values_list("section__curriculum_course__course_id", flat=True)
        )
        attempt_blocked_course_ids = _attempt_blocked_courses(student, semester)

    passed_course_ids = set(student.passed_courses().values_list("id", flat=True))
    allowed_course_ids = set(student.allowed_courses().values_list("id", flat=True))
    prereqs: Iterable[Prerequisite] = []
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
                course.id not in registered_course_ids,
                course.id not in cooldown_course_ids,
                course.id not in attempt_blocked_course_ids,
            ]
        )

        missing = [cast(str, p["label"]) for p in prereq_data if not p["met"]]
        reason = ""
        if course.id in attempt_blocked_course_ids:
            reason = "Reservation limit reached for this semester."
        elif course.id in cooldown_course_ids:
            reason = "Reservation locked for 48 hours after cancelation."
        elif course.id in registered_course_ids:
            reason = "Already reserved."
        elif not registration_open:
            reason = "Reservation window is closed."
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
    # amount_due already reflects the remaining balance after cleared payments.
    pending_registrations = (
        active_registrations.filter(status_id="pending")
        .select_related(
            "section__curriculum_course__course",
            "section__curriculum_course__credit_hours",
        )
        .prefetch_related("section__sectionfee_set")
    )
    pending_total = sum(
        (_section_fee(reg.section) for reg in pending_registrations),
        Decimal("0.00"),
    )
    outstanding = total_due + pending_total
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

    student_profile = {
        "name": student.long_name or student.user.get_full_name() or student.username,
        "student_id": student.student_id or "Pending ID",
        "academic_year": _format_semester_label(),
        "curriculum": student.curriculum.long_name or student.curriculum.short_name,
        "avatar": (
            student.photo.url if getattr(student, "photo", None) and student.photo else ""
        ),
    }

    completed_courses: list[SemesterGradeRowT] = []
    semester_grade_groups: list[SemesterGradeGroupT] = []
    semester_grade_lookup: dict[int, SemesterGradeGroupT] = {}
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
                semester_obj.start_date or date.min,
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
                "courses": [],
            }
            semester_grade_lookup[semester_id] = group
            semester_grade_groups.append(group)

        course = section.curriculum_course.course
        credits = int(section.curriculum_course.credit_hours.code)
        grade_value = grade.value
        grade_code = grade_value.code.upper() if grade_value and grade_value.code else ""

        row: SemesterGradeRowT = {
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
        if grade_value.code and grade_value.code not in GPA_EXCLUDED_CODES:
            semester_gpa_points[semester_id] += float(grade_value.number) * credits
            semester_gpa_credits[semester_id] += credits

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
        announcements.append("Reservation window is currently closed.")
    if not announcements:
        announcements.append("You are all set for the semester.")
    announcements.append(
        "Canceled reservations lock sections for 48 hours; after two attempts, "
        "the course is locked for the semester."
    )

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
        "credits_selected": 0,
        "currency": currency,
        "balance": outstanding,
    }

    sidebar_links = [
        {"label": "Dashboard", "href": reverse("student_dashboard"), "active": True},
        {"label": "Course Reservation", "href": "#courses", "active": False},
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
        "semester_grade_groups": semester_grade_groups,
        "advisor_actions": advisor_actions,
        "announcements": announcements,
        "current_semester": semester,
        "registration_open": registration_open,
        "semester_options": semester_options,
        "locked_courses": locked_courses,
    }

    return render(request, "website/student_dashboard.html", context)
