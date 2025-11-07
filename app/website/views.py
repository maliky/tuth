"""Website views for the student dashboard."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import cast

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.db.models import Avg, DecimalField, Prefetch, Q, Sum, Value, Count
from django.db.models.functions import Coalesce
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from app.academics.models.course import CurriculumCourse
from app.academics.models.prerequisite import Prerequisite
from app.finance.models.invoice import Invoice
from app.finance.models.payment import Payment
from app.people.forms.person import StudentForm
from app.people.models.student import Student
from app.registry.models.grade import Grade
from app.registry.models.registration import Registration, RegistrationStatus
from app.shared.status import StatusHistory
from app.timetable.choices import WEEKDAYS_NUMBER
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


def student_dashboard(request: HttpRequest) -> HttpResponse:
    """Render the redesigned dashboard backed with live student data."""

    student = _require_student(request.user)
    semester = student.current_enrolled_semester or get_current_semester()

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
                schedule.start_time.strftime("%H:%M") if schedule and schedule.start_time else "—"
            )
            end = schedule.end_time.strftime("%H:%M") if schedule and schedule.end_time else "—"
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
    status_summary = (
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

    available_courses = []
    for cc in curriculum_courses:
        course = cc.course
        course_sections = sections_by_course.get(course.id, [])
        prereq_data = prereq_map.get(course.id, [])
        is_eligible = course.id in allowed_course_ids and bool(course_sections)

        missing = [p["label"] for p in prereq_data if not p["met"]]
        reason = ""
        if missing:
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

        available_courses.append(
            {
                "code": course.short_code or course.code,
                "title": course.title or "",
                "credits": cc.credit_hours.code,
                "elective": cc.is_elective,
                "eligible": is_eligible,
                "reason": reason,
                "prerequisites": prereq_data,
                "sections": serialized_sections,
            }
        )

    completed_credits = student.completed_credits
    required_credits = (
        student.curriculum.programs.aggregate(total=Sum("credit_hours__code")).get("total") or 0
    )
    remaining_credits = max(required_credits - completed_credits, 0)
    gpa = Grade.objects.filter(student=student).aggregate(value=Avg("value__number")).get("value")

    invoices = Invoice.objects.filter(student=student)
    total_due = invoices.aggregate(total=Sum("amount_due")).get("total") or Decimal("0.00")
    payments = Payment.objects.filter(invoice__student=student)
    total_paid = payments.aggregate(total=Sum("amount_paid")).get("total") or Decimal("0.00")
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
        "avatar": student.photo.url if getattr(student, "photo", None) and student.photo else "",
    }

    completed_courses = []
    grades = (
        Grade.objects.filter(student=student)
        .select_related("section__curriculum_course__course", "section__curriculum_course__credit_hours", "value")
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
            f"Outstanding balance: {currency} {outstanding:.2f}. Complete payment to finalize registrations."
        )
    if semester:
        announcements.append(f"Current semester: {semester}")
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
    }

    return render(request, "website/student_dashboard.html", context)


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
        students = students.filter(
            Q(student_id__icontains=query)
            | Q(username__icontains=query)
            | Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
        )
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
