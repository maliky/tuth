"""Applicant enrollment request views."""

from __future__ import annotations

import logging
from typing import cast

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from app.academics.career_scope import (
    career_selector_context,
    filter_by_academic_career,
    selected_academic_career,
)
from app.people.models.enrollment_application import (
    EnrollmentApplication,
    EnrollmentApplicationDoc,
    EnrollmentApplicationStatus,
    EnrollmentEmailTemplate,
)
from app.registry.models.status_types import DocType
from app.shared.auth.perms import UserRole
from app.website.forms.enrollment_applications import (
    ApplicantProfileForm,
    ApplicationDocumentForm,
    EnrollmentApplicationForm,
    EnrollmentCommunicationForm,
    EnrollmentEmailTemplateForm,
    StaffApplicationReviewForm,
    VerificationCodeForm,
)
from app.website.services.enrollment_applications import (
    application_verification_token,
    application_from_token,
    approve_application,
    create_application_user,
    request_base_url,
    send_application_communication,
    send_verification_email,
)
from app.website.services.staff_portal import (
    build_staff_role_switcher,
    build_staff_sidebar_links,
)

ENROLLMENT_OFFICER_LABEL = UserRole.ENROLLMENT_OFFICER.value.label
REVIEW_SENSITIVE_FIELDS = frozenset(
    {"academic_career", "desired_academic_year", "desired_curriculum"}
)
logger = logging.getLogger(__name__)


def _as_user(request: HttpRequest) -> User:
    """Return the request user as Django's concrete user model."""
    return cast(User, request.user)


def _is_enrollment_officer(user: User) -> bool:
    """Return whether the user has officer-level enrollment authority."""
    return user.groups.filter(name=ENROLLMENT_OFFICER_LABEL).exists()


def _require_enrollment_officer(user: User) -> None:
    """Raise when the user cannot perform officer-only actions."""
    if not _is_enrollment_officer(user) and not user.is_superuser:
        raise PermissionDenied("Enrollment Officer access required.")


def _role_slug(user: User) -> str:
    """Return the active enrollment role slug for portal shell links."""
    return "enrollment_officer" if _is_enrollment_officer(user) else "enrollment"


def _staff_shell(
    request: HttpRequest,
    *,
    active_key: str,
    title: str,
) -> dict[str, object]:
    """Return common staff shell values for enrollment request screens."""
    user = _as_user(request)
    role_slug = _role_slug(user)
    career = selected_academic_career(request.GET)
    return {
        "page_title": title,
        "eyebrow": "Enrollment",
        "sidebar_links": build_staff_sidebar_links(
            role_slug,
            active_key,
            academic_career=career,
        ),
        "role_switcher": build_staff_role_switcher(
            user,
            role_slug,
            academic_career=career,
        ),
        "career_selector": career_selector_context(
            request.GET,
            action_url=request.path,
        ),
        "can_manage_requests": _is_enrollment_officer(user) or user.is_superuser,
    }


def _application_queryset(params) -> QuerySet[EnrollmentApplication]:
    """Return filtered enrollment applications for staff pages."""
    career = selected_academic_career(params)
    queryset = filter_by_academic_career(
        EnrollmentApplication.objects.select_related(
            "user",
            "desired_curriculum__college",
            "desired_entry_semester__academic_year",
            "converted_student",
        ),
        "academic_career",
        career,
    )
    q_value = str(params.get("q") or "").strip()
    if q_value:
        queryset = queryset.filter(
            Q(first_name__icontains=q_value)
            | Q(middle_name__icontains=q_value)
            | Q(last_name__icontains=q_value)
            | Q(personal_email__icontains=q_value)
            | Q(desired_curriculum__short_name__icontains=q_value)
            | Q(desired_curriculum__long_name__icontains=q_value)
            | Q(desired_curriculum__college__code__icontains=q_value)
        )
    status = str(params.get("status") or "").strip()
    if status:
        queryset = queryset.filter(status=status)
    program = str(params.get("program") or "").strip()
    if program.isdigit():
        queryset = queryset.filter(desired_curriculum_id=int(program))
    return queryset.order_by("-created_at")


def _try_send_verification(
    request: HttpRequest,
    application: EnrollmentApplication,
) -> bool:
    """Send verification mail without exposing deployment errors publicly."""
    try:
        send_verification_email(application, base_url=request_base_url(request))
    except Exception:  # pragma: no cover - deployment configuration path.
        logger.exception("Could not send enrollment verification email")
        messages.error(
            request,
            "The request was saved, but the verification email could not be sent. "
            "Try resending it in a minute.",
        )
        return False
    return True


def _reset_review_after_applicant_change(
    application: EnrollmentApplication,
    changed_fields: set[str],
) -> None:
    """Invalidate staff checks affected by an applicant-side change."""
    if not changed_fields:
        return
    application.documents_reviewed = False
    if REVIEW_SENSITIVE_FIELDS.intersection(changed_fields):
        application.placement_exam_completed = False
    if application.status == EnrollmentApplicationStatus.UNDER_REVIEW:
        application.status = EnrollmentApplicationStatus.VERIFIED


def request_enrollment(request: HttpRequest) -> HttpResponse:
    """Public applicant account and enrollment request form."""
    form = EnrollmentApplicationForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = create_application_user(
                email=form.cleaned_data["personal_email"],
                password=form.cleaned_data["password2"],
                first_name=form.cleaned_data["first_name"],
                last_name=form.cleaned_data["last_name"],
            )
            application = form.save(commit=False)
            application.user = user
            application.status = EnrollmentApplicationStatus.PENDING
            application.save()
            _save_optional_document(application, form)
        if _try_send_verification(request, application):
            messages.success(request, "Check your email for the verification code.")
        return redirect(
            "enrollment_application_verify",
            token=application_verification_token(application),
        )

    return render(
        request,
        "website/enrollment_applications/request.html",
        {"form": form, "page_title": "Request enrollment"},
    )


def _save_optional_document(
    application: EnrollmentApplication,
    form: EnrollmentApplicationForm,
) -> None:
    """Persist the optional document supplied during public signup."""
    document_file = form.cleaned_data.get("document_file")
    if not document_file:
        return
    document_type = form.cleaned_data.get("document_type") or DocType.get_dft()
    EnrollmentApplicationDoc.objects.create(
        application=application,
        data_file=document_file,
        document_type=document_type,
    )


def verify_enrollment_request(request: HttpRequest, token: str) -> HttpResponse:
    """Confirm an applicant personal email with a one-hour code."""
    try:
        application = application_from_token(token)
    except EnrollmentApplication.DoesNotExist:
        messages.error(request, "That verification link is invalid.")
        return redirect("portal_login")
    if application.is_email_verified:
        messages.info(request, "This email is already verified. You can sign in.")
        return redirect("portal_login")
    if request.method == "POST" and request.POST.get("action") == "resend":
        if not application.can_resend_verification():
            messages.warning(request, "Wait one minute before resending the code.")
        elif _try_send_verification(request, application):
            messages.success(request, "A new verification code was sent.")
        return redirect(
            "enrollment_application_verify",
            token=application_verification_token(application),
        )
    form = VerificationCodeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if application.check_verification_code(form.cleaned_data["code"]):
            application.mark_verified()
            application.save(
                update_fields=(
                    "email_verification_hash",
                    "email_verification_sent_at",
                    "email_verified_at",
                    "status",
                    "updated_at",
                )
            )
            messages.success(request, "Email verified. You can now sign in.")
            return redirect("portal_login")
        form.add_error("code", "Invalid or expired verification code.")
    return render(
        request,
        "website/enrollment_applications/verify.html",
        {"application": application, "form": form, "page_title": "Verify email"},
    )


@login_required
def applicant_dashboard(request: HttpRequest) -> HttpResponse:
    """Limited applicant portal before official student conversion."""
    user = _as_user(request)
    application = getattr(user, "enrollment_application", None)
    if application is None:
        raise PermissionDenied("No applicant record is attached to this account.")
    if application.converted_student_id:
        return redirect("student_dashboard")
    if not application.is_email_verified:
        messages.warning(request, "Confirm your email before continuing.")
        return redirect(
            "enrollment_application_verify",
            token=application_verification_token(application),
        )
    can_edit_application = application.status in {
        EnrollmentApplicationStatus.VERIFIED,
        EnrollmentApplicationStatus.UNDER_REVIEW,
    }
    if request.method == "POST" and not can_edit_application:
        raise PermissionDenied("This enrollment request can no longer be edited.")

    profile_data = request.POST if request.POST.get("action") == "profile" else None
    document_data = request.POST if request.POST.get("action") == "document" else None
    document_files = request.FILES if request.POST.get("action") == "document" else None
    profile_form = ApplicantProfileForm(
        profile_data,
        instance=application,
    )
    document_form = ApplicationDocumentForm(
        document_data,
        document_files,
    )
    if request.method == "POST" and request.POST.get("action") == "profile":
        if profile_form.is_valid():
            changed_fields = set(profile_form.changed_data)
            application = profile_form.save(commit=False)
            _reset_review_after_applicant_change(application, changed_fields)
            application.save()
            user.email = application.personal_email
            user.first_name = application.first_name
            user.last_name = application.last_name
            user.save(update_fields=("email", "first_name", "last_name"))
            messages.success(request, "Application updated.")
            return redirect("applicant_dashboard")
    elif request.method == "POST" and request.POST.get("action") == "document":
        if document_form.is_valid():
            doc = document_form.save(commit=False)
            doc.application = application
            doc.save()
            _reset_review_after_applicant_change(application, {"documents"})
            application.save(
                update_fields=(
                    "documents_reviewed",
                    "placement_exam_completed",
                    "status",
                    "updated_at",
                )
            )
            messages.success(request, "Document uploaded.")
            return redirect("applicant_dashboard")

    return render(
        request,
        "website/enrollment_applications/applicant_dashboard.html",
        {
            "application": application,
            "profile_form": profile_form,
            "document_form": document_form,
            "documents": application.documents.select_related("document_type", "status"),
            "communications": application.communications.select_related("sender")[:10],
            "can_edit_application": can_edit_application,
            "page_title": "Enrollment request",
            "eyebrow": "Applicant portal",
            "sidebar_links": [
                {
                    "label": "Application",
                    "href": reverse("applicant_dashboard"),
                    "active": True,
                    "icon": "bi-file-earmark-person",
                }
            ],
        },
    )


@permission_required("people.view_enrollmentapplication", raise_exception=True)
def enrollment_applications(request: HttpRequest) -> HttpResponse:
    """List enrollment applications visible to enrollment staff."""
    queryset = _application_queryset(request.GET)
    page_obj = Paginator(queryset, 25).get_page(request.GET.get("page"))
    context = _staff_shell(
        request,
        active_key="enrollment_requests",
        title="Enrollment requests",
    )
    context.update(
        {
            "applications": page_obj.object_list,
            "page_obj": page_obj,
            "statuses": EnrollmentApplicationStatus.choices,
            "filters": request.GET,
        }
    )
    return render(request, "enrollment/applications/list.html", context)


@permission_required("people.view_enrollmentapplication", raise_exception=True)
def enrollment_application_detail(
    request: HttpRequest,
    application_id: int,
) -> HttpResponse:
    """Review one enrollment application."""
    application = get_object_or_404(
        EnrollmentApplication.objects.select_related(
            "desired_curriculum__college",
            "desired_entry_semester__academic_year",
            "converted_student",
            "user",
        ),
        pk=application_id,
    )
    user = _as_user(request)
    review_form = StaffApplicationReviewForm(request.POST or None, instance=application)
    if request.method == "POST":
        _require_enrollment_officer(user)
        action = request.POST.get("action")
        if action == "approve":
            try:
                student = approve_application(application, user)
                messages.success(request, f"Approved and created {student.student_id}.")
                return redirect("std_detail", pk=student.pk)
            except ValueError as exc:
                messages.error(request, str(exc))
        elif action == "reject":
            application.status = EnrollmentApplicationStatus.REJECTED
            application.review_notes = request.POST.get("review_notes", "")
            application.save(update_fields=("status", "review_notes", "updated_at"))
            messages.success(request, "Application rejected.")
            return redirect(
                "enrollment_application_detail", application_id=application.pk
            )
        elif review_form.is_valid():
            review_form.save()
            messages.success(request, "Review saved.")
            return redirect(
                "enrollment_application_detail", application_id=application.pk
            )

    context = _staff_shell(
        request,
        active_key="enrollment_requests",
        title=application.full_name,
    )
    context.update(
        {
            "application": application,
            "review_form": review_form,
            "documents": application.documents.select_related("document_type", "status"),
            "communications": application.communications.select_related("sender")[:10],
        }
    )
    return render(request, "enrollment/applications/detail.html", context)


@permission_required("people.change_enrollmentemailtemplate", raise_exception=True)
def enrollment_email_template(request: HttpRequest) -> HttpResponse:
    """Edit the applicant verification email template."""
    _require_enrollment_officer(_as_user(request))
    template = EnrollmentEmailTemplate.verification_template()
    form = EnrollmentEmailTemplateForm(request.POST or None, instance=template)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Verification email template updated.")
        return redirect("enrollment_email_template")
    context = _staff_shell(
        request,
        active_key="enrollment_email_template",
        title="Enrollment email template",
    )
    context.update({"form": form, "template": template})
    return render(request, "enrollment/applications/email_template.html", context)


@permission_required("people.add_enrollmentcommunication", raise_exception=True)
def enrollment_communications(request: HttpRequest) -> HttpResponse:
    """Send communications to selected or filtered applicants."""
    _require_enrollment_officer(_as_user(request))
    queryset = _application_queryset(request.GET)
    form = EnrollmentCommunicationForm(
        request.POST or None,
        queryset=queryset,
    )
    if request.method == "POST" and form.is_valid():
        selected = form.cleaned_data["selected_applications"]
        recipients = queryset if form.cleaned_data["send_to_filtered"] else selected
        rows = send_application_communication(
            applications=recipients,
            sender=_as_user(request),
            subject=form.cleaned_data["subject"],
            body=form.cleaned_data["body"],
        )
        sent_count = sum(1 for row in rows if row.email_sent)
        failed_count = len(rows) - sent_count
        if sent_count:
            messages.success(request, f"Sent {sent_count} communication(s).")
        if failed_count:
            messages.warning(
                request,
                f"Stored {failed_count} communication(s) that could not be emailed.",
            )
        return redirect("enrollment_communications")
    context = _staff_shell(
        request,
        active_key="enrollment_communications",
        title="Applicant communications",
    )
    context.update(
        {
            "form": form,
            "applications": queryset[:50],
            "statuses": EnrollmentApplicationStatus.choices,
            "filters": request.GET,
        }
    )
    return render(request, "enrollment/applications/communications.html", context)


__all__ = [
    "applicant_dashboard",
    "enrollment_application_detail",
    "enrollment_applications",
    "enrollment_communications",
    "enrollment_email_template",
    "request_enrollment",
    "verify_enrollment_request",
]
