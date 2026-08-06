"""Services for applicant enrollment requests."""

from __future__ import annotations

from typing import Iterable, TypeAlias, cast

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.core.signing import BadSignature, Signer
from django.db import transaction
from django.urls import reverse

from app.academics.models.curriculum import Curriculum
from app.people.models.enrollment_application import (
    EnrollmentApplication,
    EnrollmentApplicationDoc,
    EnrollmentApplicationStatus,
    EnrollmentCommunication,
    EnrollmentEmailTemplate,
    enrollment_default_from_email,
)
from app.people.models.student import Student
from app.people.models.student_curriculum_enrollment import set_primary_std_curri_enroll
from app.registry.models.document import DocStd
from app.shared.auth.perms import UserRole

APPLICATION_TOKEN_SALT = "tusis.enrollment.application"
TemplateContextT: TypeAlias = dict[str, str]


def unique_applicant_username(email: str) -> str:
    """Return a deterministic username derived from the applicant email."""
    seed = email.split("@", 1)[0].lower().replace(".", "_") or "applicant"
    username = seed[:42]
    counter = 1
    while User.objects.filter(username=username).exists():
        counter += 1
        username = f"{seed[:38]}_{counter}"
    return username


def application_verification_token(application: EnrollmentApplication) -> str:
    """Return a signed token identifying one enrollment request."""
    return Signer(salt=APPLICATION_TOKEN_SALT).sign(str(application.pk))


def application_from_token(token: str) -> EnrollmentApplication:
    """Resolve a signed verification token into an application."""
    try:
        value = Signer(salt=APPLICATION_TOKEN_SALT).unsign(token)
    except BadSignature as exc:
        raise EnrollmentApplication.DoesNotExist from exc
    return EnrollmentApplication.objects.select_related("desired_curriculum").get(
        pk=value
    )


def verification_url(application: EnrollmentApplication, base_url: str) -> str:
    """Return an absolute verification URL for an enrollment request."""
    path = reverse(
        "enrollment_application_verify",
        args=[application_verification_token(application)],
    )
    return f"{base_url.rstrip('/')}{path}"


def template_context(
    application: EnrollmentApplication,
    *,
    code: str,
    verification_url_value: str,
) -> TemplateContextT:
    """Return string placeholders for applicant emails."""
    curriculum = application.desired_curriculum
    return {
        "applicant_name": application.full_name,
        "code": code,
        "career": application.get_academic_career_display(),
        "program": curriculum.long_name or curriculum.short_name,
        "username": application.user.username,
        "verification_url": verification_url_value,
    }


def _ensure_username_reminder(body: str, username: str) -> str:
    """Append the applicant username when a legacy template omits it."""
    if username and username not in body:
        return f"{body.rstrip()}\n\nUsername: {username}"
    return body


def send_verification_email(
    application: EnrollmentApplication,
    *,
    base_url: str,
) -> None:
    """Generate, persist, and email a one-hour verification code."""
    code = EnrollmentApplication.generate_verification_code()
    application.set_verification_code(code)
    application.save(
        update_fields=("email_verification_hash", "email_verification_sent_at")
    )
    template = EnrollmentEmailTemplate.verification_template()
    context = template_context(
        application,
        code=code,
        verification_url_value=verification_url(application, base_url),
    )
    subject = template.subject.format(**context)
    body = _ensure_username_reminder(
        template.body.format(**context),
        application.user.username,
    )
    send_mail(
        subject,
        body,
        enrollment_default_from_email(),
        [application.personal_email],
        fail_silently=False,
    )


@transaction.atomic
def create_application_user(
    *,
    email: str,
    password: str,
    first_name: str,
    last_name: str,
) -> User:
    """Create a prospecting student user account."""
    user = User.objects.create_user(
        username=unique_applicant_username(email),
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
    )
    user.groups.add(UserRole.PROSPECTING_STUDENT.value.group)
    return user


@transaction.atomic
def approve_application(application: EnrollmentApplication, reviewer: User) -> Student:
    """Convert a reviewed application into an official Student."""
    # Lock only the application row; nullable joins cannot be locked on PostgreSQL.
    application = EnrollmentApplication.objects.select_for_update().get(pk=application.pk)
    if application.converted_student_id:
        existing_student = application.converted_student
        if existing_student is None:
            raise ValueError("Converted student record is missing.")
        return existing_student
    if not application.can_approve():
        raise ValueError("Enrollment application is not ready for approval.")

    user = application.user
    user.first_name = application.first_name
    user.last_name = application.last_name
    user.email = application.personal_email
    user.groups.add(UserRole.STUDENT.value.group)
    user.groups.remove(UserRole.PROSPECTING_STUDENT.value.group)
    user.save(update_fields=("first_name", "last_name", "email"))

    student = Student(
        user=user,
        academic_career=application.academic_career,
        entry_semester=application.desired_entry_semester,
        last_enrolled_semester=application.desired_entry_semester,
        prefix_name=application.prefix_name,
        middle_name=application.middle_name,
        suffix_name=application.suffix_name,
        phone_number=application.phone_number,
        physical_address=application.physical_address,
        birth_date=application.birth_date,
        birth_place=application.birth_place,
        gender=application.gender,
        nationality=application.nationality,
        origin_county=application.origin_county,
        marital_status=application.marital_status,
        last_school_attended=application.last_school_attended,
        reason_for_leaving=application.reason_for_leaving,
        father_name=application.father_name,
        father_address=application.father_address,
        mother_name=application.mother_name,
        mother_address=application.mother_address,
        emergency_contact=application.emergency_contact,
    )
    student.save()
    set_primary_std_curri_enroll(
        student,
        application.desired_curriculum,
        entry_semester_id=application.desired_entry_semester_id,
        is_active=True,
    )
    _transfer_documents(application, student)
    application.converted_student = student
    application.status = EnrollmentApplicationStatus.APPROVED
    application.review_notes = _append_note(
        application.review_notes,
        f"Approved by {reviewer.username}.",
    )
    application.save(
        update_fields=("converted_student", "status", "review_notes", "updated_at")
    )
    return student


def _transfer_documents(application: EnrollmentApplication, student: Student) -> None:
    """Copy application document references onto official student documents."""
    for doc in application.documents.select_related("document_type", "status"):
        DocStd.objects.get_or_create(
            person=student,
            data_file=doc.data_file.name,
            document_type=doc.document_type,
            defaults={"status": doc.status},
        )


def _append_note(current: str, note: str) -> str:
    """Append a one-line audit note to review notes."""
    return "\n".join(part for part in (current.strip(), note) if part)


def send_application_communication(
    *,
    applications: Iterable[EnrollmentApplication],
    sender: User,
    subject: str,
    body: str,
) -> list[EnrollmentCommunication]:
    """Send and store one communication for each selected applicant."""
    rows: list[EnrollmentCommunication] = []
    from_email = enrollment_default_from_email()
    for application in applications:
        sent = False
        error_message = ""
        try:
            send_mail(
                subject,
                body,
                from_email,
                [application.personal_email],
                fail_silently=False,
            )
            sent = True
        except Exception as exc:  # pragma: no cover - exercised by deployment smoke.
            error_message = str(exc)
        rows.append(
            EnrollmentCommunication.objects.create(
                application=application,
                sender=sender,
                subject=subject,
                body=body,
                email_sent=sent,
                error_message=error_message,
            )
        )
    return rows


def request_base_url(request) -> str:
    """Return a base URL suitable for email links."""
    configured = getattr(settings, "TUSIS_PUBLIC_BASE_URL", "")
    if configured:
        return configured
    return f"{request.scheme}://{request.get_host()}"


def active_application_exists(email: str) -> bool:
    """Return whether an email is already attached to an active applicant/student."""
    active_statuses = [
        EnrollmentApplicationStatus.PENDING,
        EnrollmentApplicationStatus.VERIFIED,
        EnrollmentApplicationStatus.UNDER_REVIEW,
        EnrollmentApplicationStatus.APPROVED,
    ]
    return bool(
        EnrollmentApplication.objects.filter(
            personal_email__iexact=email,
            status__in=active_statuses,
        ).exists()
        or Student.objects.filter(user__email__iexact=email).exists()
    )


def application_program_queryset(career: str):
    """Return active curricula for the selected applicant career."""
    return Curriculum.objects.filter(
        academic_career=career,
        is_active=True,
    ).select_related("college")


__all__ = [
    "active_application_exists",
    "application_from_token",
    "application_program_queryset",
    "approve_application",
    "create_application_user",
    "request_base_url",
    "send_application_communication",
    "send_verification_email",
]
