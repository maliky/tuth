"""Applicant-side enrollment request models."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from secrets import randbelow
from typing import TYPE_CHECKING

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse
from django.utils import timezone
from simple_history.models import HistoricalRecords

from app.academics.choices import AcademicCareer
from app.registry.models.status_types import DocStatus, DocType

if TYPE_CHECKING:
    from app.timetable.models.academic_year import AcademicYear


VERIFICATION_EXPIRY = timedelta(hours=1)
VERIFICATION_RESEND_DELAY = timedelta(minutes=1)
DEFAULT_VERIFICATION_EMAIL_BODY = (
    "Dear {applicant_name},\n\n"
    "Use this code to confirm your enrollment request: {code}\n\n"
    "The code expires in 1 hour.\n\n"
    "Username: {username}\n"
    "Program: {program}\n"
    "Career: {career}\n"
    "Verification link: {verification_url}\n\n"
    "Tubman University Enrollment"
)


class EnrollmentApplicationStatus(models.TextChoices):
    """Workflow states for applicant enrollment requests."""

    PENDING = "pending", "Pending"
    VERIFIED = "verified", "Email verified"
    UNDER_REVIEW = "under_review", "Under review"
    REJECTED = "rejected", "Rejected"
    APPROVED = "approved", "Approved"


def application_document_path(instance: "EnrollmentApplicationDoc", filename: str) -> str:
    """Return a stable upload path for applicant documents."""
    app_id = instance.application_id or "pending"
    return str(Path("enrollment_applications") / str(app_id) / filename)


class EnrollmentApplication(models.Model):
    """Pending enrollment request submitted before final student creation."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="enrollment_application",
    )
    personal_email = models.EmailField(db_index=True)
    desired_curriculum = models.ForeignKey(
        "academics.Curriculum",
        on_delete=models.PROTECT,
        related_name="enrollment_applications",
    )
    desired_entry_semester = models.ForeignKey(
        "timetable.Semester",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="enrollment_applications",
    )
    academic_career = models.CharField(
        max_length=20,
        choices=AcademicCareer.choices,
        default=AcademicCareer.UNDERGRADUATE,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=EnrollmentApplicationStatus.choices,
        default=EnrollmentApplicationStatus.PENDING,
        db_index=True,
    )
    email_verification_hash = models.CharField(max_length=128, blank=True)
    email_verification_sent_at = models.DateTimeField(null=True, blank=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    documents_reviewed = models.BooleanField(default=False)
    placement_exam_completed = models.BooleanField(default=False)
    review_notes = models.TextField(blank=True)
    converted_student = models.OneToOneField(
        "people.Student",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_enrollment_application",
    )
    prefix_name = models.CharField(blank=True)
    first_name = models.CharField(max_length=150)
    middle_name = models.CharField(blank=True)
    last_name = models.CharField(max_length=150)
    suffix_name = models.CharField(blank=True)
    phone_number = models.CharField(blank=True)
    physical_address = models.TextField(blank=True)
    birth_date = models.DateField(null=True, blank=True)
    birth_place = models.CharField(blank=True)
    gender = models.CharField(choices=[("f", "Female"), ("m", "Male")], blank=True)
    nationality = models.CharField(blank=True)
    origin_county = models.CharField(blank=True)
    marital_status = models.CharField(blank=True)
    last_school_attended = models.CharField(blank=True)
    reason_for_leaving = models.TextField(blank=True)
    father_name = models.CharField(blank=True)
    father_address = models.TextField(blank=True)
    mother_name = models.CharField(blank=True)
    mother_address = models.TextField(blank=True)
    emergency_contact = models.CharField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("status", "academic_career")),
            models.Index(fields=("personal_email", "status")),
        ]

    def __str__(self) -> str:
        """Return a readable applicant label."""
        return f"{self.full_name} ({self.personal_email})"

    @property
    def full_name(self) -> str:
        """Return the applicant's formatted name."""
        parts = [
            self.prefix_name,
            self.first_name,
            self.middle_name,
            self.last_name,
            self.suffix_name,
        ]
        return " ".join(part for part in parts if part).strip()

    @property
    def desired_program_name(self) -> str:
        """Return the desired curriculum as a public-facing program name."""
        return str(
            self.desired_curriculum.long_name or self.desired_curriculum.short_name
        )

    @property
    def desired_academic_year(self) -> AcademicYear | None:
        """Return the academic year selected through the applicant form."""
        semester = self.desired_entry_semester
        if semester is None:
            return None
        return semester.academic_year

    @property
    def is_email_verified(self) -> bool:
        """Return whether the applicant has confirmed their personal email."""
        return self.email_verified_at is not None

    @property
    def verification_expires_at(self) -> datetime | None:
        """Return the timestamp at which the current code expires."""
        if not self.email_verification_sent_at:
            return None
        return self.email_verification_sent_at + VERIFICATION_EXPIRY

    def verification_expired(self) -> bool:
        """Return whether the current verification code is expired."""
        expires_at = self.verification_expires_at
        return expires_at is None or timezone.now() > expires_at

    def set_verification_code(self, code: str) -> None:
        """Hash and timestamp a new verification code."""
        self.email_verification_hash = make_password(code)
        self.email_verification_sent_at = timezone.now()

    def check_verification_code(self, code: str) -> bool:
        """Validate a submitted verification code against the current hash."""
        if self.verification_expired() or not self.email_verification_hash:
            return False
        return check_password(code, self.email_verification_hash)

    def can_resend_verification(self) -> bool:
        """Return whether another verification message can be sent."""
        sent_at = self.email_verification_sent_at
        return sent_at is None or timezone.now() >= sent_at + VERIFICATION_RESEND_DELAY

    def mark_verified(self) -> None:
        """Mark the personal email as verified."""
        self.email_verified_at = timezone.now()
        self.email_verification_hash = ""
        self.email_verification_sent_at = None
        if self.status == EnrollmentApplicationStatus.PENDING:
            self.status = EnrollmentApplicationStatus.VERIFIED

    def can_approve(self) -> bool:
        """Return whether staff can convert this request into a Student."""
        return bool(
            self.is_email_verified
            and self.documents_reviewed
            and self.placement_exam_completed
            and self.status
            in {
                EnrollmentApplicationStatus.VERIFIED,
                EnrollmentApplicationStatus.UNDER_REVIEW,
            }
            and self.desired_entry_semester_id is not None
            and self.desired_curriculum.academic_career == self.academic_career
            and self.converted_student_id is None
        )

    def applicant_url(self) -> str:
        """Return the applicant portal URL."""
        return reverse("applicant_dashboard")

    @classmethod
    def generate_verification_code(cls) -> str:
        """Return a six-digit email verification code."""
        return f"{randbelow(1_000_000):06d}"


class EnrollmentApplicationDoc(models.Model):
    """Document uploaded against a pending enrollment request."""

    application = models.ForeignKey(
        EnrollmentApplication,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    data_file = models.FileField(upload_to=application_document_path)
    status = models.ForeignKey(
        DocStatus,
        on_delete=models.PROTECT,
        related_name="enrollment_application_docs",
    )
    document_type = models.ForeignKey(
        DocType,
        on_delete=models.PROTECT,
        related_name="enrollment_application_docs",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ("-uploaded_at", "-id")

    def __str__(self) -> str:
        """Return a compact document label."""
        return f"{self.application.full_name} - {self.document_type}"

    def save(self, *args, **kwargs):
        """Apply default document lookup rows before saving."""
        if not self.status_id:
            self.status = DocStatus.get_dft()
        if not self.document_type_id:
            self.document_type = DocType.get_dft()
        return super().save(*args, **kwargs)


class EnrollmentEmailTemplate(models.Model):
    """Editable email text used for enrollment request verification."""

    code = models.CharField(max_length=50, unique=True)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("code",)

    def __str__(self) -> str:
        """Return the template label."""
        return self.code

    @classmethod
    def verification_template(cls) -> "EnrollmentEmailTemplate":
        """Return the default verification email template."""
        template, _created = cls.objects.get_or_create(
            code="applicant_verification",
            defaults={
                "subject": "Confirm your TUSIS enrollment request",
                "body": DEFAULT_VERIFICATION_EMAIL_BODY,
            },
        )
        if "{username}" not in template.body:
            template.body = f"{template.body.rstrip()}\n\nUsername: {{username}}"
            template.save(update_fields=("body", "updated_at"))
        return template


class EnrollmentCommunication(models.Model):
    """Message sent by enrollment staff to one applicant."""

    application = models.ForeignKey(
        EnrollmentApplication,
        on_delete=models.CASCADE,
        related_name="communications",
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="sent_enrollment_communications",
    )
    subject = models.CharField(max_length=255)
    body = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    email_sent = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ("-sent_at", "-id")

    def __str__(self) -> str:
        """Return a compact communication label."""
        return f"{self.application.personal_email}: {self.subject}"


def enrollment_default_from_email() -> str:
    """Return the sender configured for enrollment email."""
    return getattr(settings, "ENROLLMENT_DEFAULT_FROM_EMAIL", settings.DEFAULT_FROM_EMAIL)


__all__ = [
    "EnrollmentApplication",
    "EnrollmentApplicationDoc",
    "EnrollmentApplicationStatus",
    "EnrollmentCommunication",
    "EnrollmentEmailTemplate",
    "DEFAULT_VERIFICATION_EMAIL_BODY",
    "VERIFICATION_EXPIRY",
    "VERIFICATION_RESEND_DELAY",
    "enrollment_default_from_email",
]
