"""Safety regressions for applicant enrollment requests."""

from __future__ import annotations

from datetime import timedelta
from importlib import import_module

import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from app.academics.models.curriculum import Curriculum
from app.people.models.enrollment_application import (
    EnrollmentApplication,
    EnrollmentApplicationStatus,
)
from app.people.models.student import Student
from app.registry.models.status_types import DocType
from app.website.forms.enrollment_applications import (
    EnrollmentApplicationForm,
    EnrollmentEmailTemplateForm,
)
from app.website.services.enrollment_applications import application_verification_token
from tests.website.test_enrollment_applications import (
    _career_program,
    _group_user,
    _perm,
    _request_payload,
)

pytestmark = pytest.mark.django_db


def _reviewed_application(
    status: str = EnrollmentApplicationStatus.UNDER_REVIEW,
) -> EnrollmentApplication:
    """Create one verified application with completed staff checks."""
    curriculum, semester = _career_program()
    user = User.objects.create_user(
        "safety_applicant",
        email="verified@example.test",
        password="ApplicantPassW0rd!",
    )
    _group_user(user, "Prospecting Student")
    return EnrollmentApplication.objects.create(
        user=user,
        personal_email="verified@example.test",
        desired_curriculum=curriculum,
        desired_entry_semester=semester,
        academic_career=curriculum.academic_career,
        status=status,
        email_verified_at=timezone.now(),
        documents_reviewed=True,
        placement_exam_completed=True,
        first_name="Safety",
        last_name="Applicant",
    )


def _profile_payload(
    application: EnrollmentApplication,
    curriculum: Curriculum,
) -> dict[str, str]:
    """Return an applicant profile update payload."""
    return {
        "action": "profile",
        "personal_email": "replacement@example.test",
        "academic_career": application.academic_career,
        "desired_curriculum": str(curriculum.pk),
        "desired_academic_year": str(application.desired_academic_year.pk),
        "first_name": "Updated",
        "last_name": application.last_name,
    }


def test_profile_change_keeps_verified_email_and_invalidates_review(client) -> None:
    """Applicant edits should preserve identity and invalidate stale staff checks."""
    application = _reviewed_application()
    curriculum = Curriculum.objects.create(
        college=application.desired_curriculum.college,
        short_name="GRAD-SAFE-2",
        long_name="Second Applicant Program",
        status=application.desired_curriculum.status,
        is_active=True,
        academic_career=application.academic_career,
    )
    client.force_login(application.user)

    response = client.post(
        reverse("applicant_dashboard"),
        _profile_payload(application, curriculum),
    )

    assert response.status_code == 302
    application.refresh_from_db()
    application.user.refresh_from_db()
    assert application.personal_email == "verified@example.test"
    assert application.user.email == "verified@example.test"
    assert application.desired_curriculum == curriculum
    assert application.status == EnrollmentApplicationStatus.VERIFIED
    assert not application.documents_reviewed
    assert not application.placement_exam_completed


def test_document_upload_invalidates_document_review(client) -> None:
    """A new applicant document should require another staff review."""
    application = _reviewed_application()
    doc_type, _created = DocType.objects.get_or_create(
        code="safety-doc",
        defaults={"label": "Safety document"},
    )
    client.force_login(application.user)

    response = client.post(
        reverse("applicant_dashboard"),
        {
            "action": "document",
            "document_type": str(doc_type.pk),
            "data_file": SimpleUploadedFile("safety.pdf", b"pdf"),
        },
    )

    assert response.status_code == 302
    application.refresh_from_db()
    assert application.status == EnrollmentApplicationStatus.VERIFIED
    assert not application.documents_reviewed
    assert application.placement_exam_completed


def test_rejected_application_is_read_only_and_cannot_be_approved(client) -> None:
    """A rejected request should stay rejected until a new workflow is started."""
    application = _reviewed_application(EnrollmentApplicationStatus.REJECTED)
    client.force_login(application.user)
    edit_response = client.post(
        reverse("applicant_dashboard"),
        _profile_payload(application, application.desired_curriculum),
    )
    assert edit_response.status_code == 403

    officer = User.objects.create_user("safety_officer", password="PassW0rd!")
    _group_user(officer, "Enrollment Officer")
    officer.user_permissions.add(
        _perm("people", "view_enrollmentapplication"),
        _perm("people", "change_enrollmentapplication"),
    )
    client.force_login(officer)
    approval_response = client.post(
        reverse("enrollment_application_detail", args=[application.pk]),
        {"action": "approve"},
    )

    assert approval_response.status_code == 200
    application.refresh_from_db()
    assert application.status == EnrollmentApplicationStatus.REJECTED
    assert application.converted_student is None
    assert not Student.objects.filter(user=application.user).exists()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_expired_verification_code_can_be_resent_with_cooldown(client) -> None:
    """Applicants should recover from expiration without mail flooding."""
    curriculum, semester = _career_program()
    client.post(reverse("request_enrollment"), _request_payload(curriculum, semester))
    application = EnrollmentApplication.objects.get()
    original_hash = application.email_verification_hash
    application.email_verification_sent_at = timezone.now() - timedelta(minutes=2)
    application.save(update_fields=("email_verification_sent_at",))
    url = reverse(
        "enrollment_application_verify",
        args=[application_verification_token(application)],
    )

    response = client.post(url, {"action": "resend"})

    assert response.status_code == 302
    application.refresh_from_db()
    assert len(mail.outbox) == 2
    assert application.email_verification_hash != original_hash

    cooldown_response = client.post(url, {"action": "resend"}, follow=True)
    assert cooldown_response.status_code == 200
    assert len(mail.outbox) == 2
    assert "Wait one minute" in cooldown_response.content.decode()


def test_email_template_rejects_unknown_and_malformed_placeholders() -> None:
    """Editable mail templates should not break runtime formatting."""
    unknown = EnrollmentEmailTemplateForm(
        data={
            "subject": "Hello {unknown}",
            "body": "Code {code}; username {username}",
        }
    )
    malformed = EnrollmentEmailTemplateForm(
        data={
            "subject": "Hello {applicant_name",
            "body": "Code {code}; username {username}",
        }
    )

    assert not unknown.is_valid()
    assert "Unsupported placeholders" in str(unknown.errors["subject"])
    assert not malformed.is_valid()
    assert "formatting is invalid" in str(malformed.errors["subject"])


def test_request_creation_rolls_back_user_when_application_save_fails(
    client,
    monkeypatch,
) -> None:
    """A failed application save should not leave an orphan login account."""
    curriculum, semester = _career_program()

    def fail_save(_form, commit=True):
        raise RuntimeError("application-save-failed")

    monkeypatch.setattr(EnrollmentApplicationForm, "save", fail_save)
    with pytest.raises(RuntimeError, match="application-save-failed"):
        client.post(
            reverse("request_enrollment"),
            _request_payload(curriculum, semester),
        )

    assert not User.objects.filter(email="applicant@example.test").exists()
    assert not EnrollmentApplication.objects.exists()


def test_public_mail_failure_is_generic(client, monkeypatch) -> None:
    """SMTP details should be logged, not shown to public applicants."""
    curriculum, semester = _career_program()

    def fail_send(*_args, **_kwargs):
        raise RuntimeError("smtp-private-detail")

    views_module = import_module("app.website.views.enrollment_applications")
    monkeypatch.setattr(views_module, "send_verification_email", fail_send)
    response = client.post(
        reverse("request_enrollment"),
        _request_payload(curriculum, semester),
        follow=True,
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert EnrollmentApplication.objects.exists()
    assert "verification email could not be sent" in content
    assert "smtp-private-detail" not in content
