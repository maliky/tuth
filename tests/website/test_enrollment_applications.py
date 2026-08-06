"""Tests for public enrollment requests and applicant review."""

from __future__ import annotations

import re
from datetime import date

import pytest
from django.contrib.auth.models import Group, Permission, User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from app.academics.choices import AcademicCareer
from app.academics.models.college import College
from app.academics.models.curriculum import Curriculum, CurriStatus
from app.people.models.enrollment_application import (
    EnrollmentApplication,
    EnrollmentApplicationDoc,
    EnrollmentApplicationStatus,
)
from app.people.models.student import Student
from app.registry.models.document import DocStd
from app.registry.models.status_types import DocStatus, DocType
from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.semester import Semester, SemesterStatus
from app.website.services.enrollment_applications import application_verification_token

pytestmark = pytest.mark.django_db


def _perm(app_label: str, codename: str) -> Permission:
    """Return a concrete model permission."""
    return Permission.objects.get(content_type__app_label=app_label, codename=codename)


def _group_user(user: User, group_name: str) -> None:
    """Attach a user to a portal role group."""
    group, _created = Group.objects.get_or_create(name=group_name)
    user.groups.add(group)


def _career_program(career: str = AcademicCareer.GRADUATE) -> tuple[Curriculum, Semester]:
    """Create one active curriculum and matching semester."""
    college = College.objects.create(
        code=f"T{career[:2].upper()}", long_name="Test College"
    )
    status, _created = CurriStatus.objects.get_or_create(
        code="approved",
        defaults={"label": "Approved"},
    )
    curriculum = Curriculum.objects.create(
        short_name=f"{career[:4].upper()}-APP",
        long_name="Applicant Program",
        college=college,
        status=status,
        is_active=True,
        academic_career=career,
    )
    academic_year = AcademicYear.objects.create(
        code="26-27",
        start_date=date(2026, 8, 1),
    )
    semester_status, _created = SemesterStatus.objects.get_or_create(
        code="registration",
        defaults={"label": "Registration open"},
    )
    semester = Semester.objects.create(
        academic_year=academic_year,
        number=1,
        academic_career=career,
        status=semester_status,
    )
    return curriculum, semester


def _request_payload(curriculum: Curriculum, semester: Semester) -> dict[str, str]:
    """Return a valid public request payload."""
    return {
        "personal_email": "applicant@example.test",
        "password1": "ApplicantPassW0rd!",
        "password2": "ApplicantPassW0rd!",
        "academic_career": curriculum.academic_career,
        "desired_curriculum": str(curriculum.id),
        "desired_academic_year": str(semester.academic_year_id),
        "first_name": "Ada",
        "middle_name": "M",
        "last_name": "Applicant",
        "phone_number": "+231770000010",
        "birth_date": "2000-01-02",
        "gender": "f",
        "nationality": "Liberian",
        "origin_county": "Maryland",
        "last_school_attended": "Test School",
        "emergency_contact": "Contact",
    }


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_public_request_creates_application_and_sends_verification_email(client) -> None:
    """Public enrollment request should create only a pending application."""
    curriculum, semester = _career_program()

    response = client.post(
        reverse("request_enrollment"),
        _request_payload(curriculum, semester),
    )

    assert response.status_code == 302
    application = EnrollmentApplication.objects.get()
    assert application.personal_email == "applicant@example.test"
    assert application.status == EnrollmentApplicationStatus.PENDING
    assert application.converted_student is None
    assert not Student.objects.filter(user=application.user).exists()
    assert application.user.groups.filter(name="Prospecting Student").exists()
    assert len(mail.outbox) == 1
    assert re.search(r"\b\d{6}\b", str(mail.outbox[0].body))
    assert f"Username: {application.user.username}" in str(mail.outbox[0].body)


def test_public_request_form_is_minimal_and_program_named(client) -> None:
    """The public request page should expose account fields, not the full profile."""
    curriculum, _semester = _career_program()

    response = client.get(reverse("request_enrollment"))

    content = response.content.decode()
    assert response.status_code == 200
    assert "Desired program" in content
    assert "Desired curriculum" not in content
    assert "Academic year" in content
    assert "Entry semester" not in content
    assert curriculum.long_name in content
    assert "Phone number" not in content
    assert "Document file" not in content
    assert '<span class="text-danger ms-1">*</span>' in content


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_verification_enables_limited_applicant_portal(client) -> None:
    """A verified applicant should be routed to the applicant portal."""
    curriculum, semester = _career_program()
    client.post(reverse("request_enrollment"), _request_payload(curriculum, semester))
    application = EnrollmentApplication.objects.get()
    code_match = re.search(r"\b\d{6}\b", str(mail.outbox[0].body))
    assert code_match is not None
    code = code_match.group(0)

    response = client.post(
        reverse(
            "enrollment_application_verify",
            args=[application_verification_token(application)],
        ),
        {"code": code},
    )
    assert response.status_code == 302
    application.refresh_from_db()
    assert application.is_email_verified
    assert application.email_verification_hash == ""
    assert application.email_verification_sent_at is None

    client.login(username=application.user.username, password="ApplicantPassW0rd!")
    redirect_response = client.get(reverse("portal_redirect"))
    assert redirect_response.status_code == 302
    assert redirect_response.headers["Location"] == reverse("applicant_dashboard")
    dashboard_response = client.get(reverse("applicant_dashboard"))
    assert dashboard_response.status_code == 200
    assert "Enrollment request" in dashboard_response.content.decode()


def test_enrollment_staff_can_view_requests_but_only_officer_manages(client) -> None:
    """Enrollment users can inspect applications; officers see management actions."""
    curriculum, semester = _career_program()
    user = User.objects.create_user("view_applicant", password="PassW0rd!")
    _group_user(user, "Enrollment")
    user.user_permissions.add(_perm("people", "view_enrollmentapplication"))
    EnrollmentApplication.objects.create(
        user=User.objects.create_user("applicant_view"),
        personal_email="view@example.test",
        desired_curriculum=curriculum,
        desired_entry_semester=semester,
        academic_career=curriculum.academic_career,
        first_name="View",
        last_name="Applicant",
    )
    client.force_login(user)

    response = client.get(reverse("enrollment_applications"))
    assert response.status_code == 200
    assert "view@example.test" in response.content.decode()

    officer = User.objects.create_user("officer_applicant", password="PassW0rd!")
    _group_user(officer, "Enrollment Officer")
    officer.user_permissions.add(
        _perm("people", "view_enrollmentapplication"),
        _perm("people", "change_enrollmentemailtemplate"),
        _perm("people", "add_enrollmentcommunication"),
    )
    client.force_login(officer)
    assert client.get(reverse("enrollment_email_template")).status_code == 200
    assert client.get(reverse("enrollment_communications")).status_code == 200


@override_settings(MEDIA_ROOT="/tmp/tusis-test-media")
def test_officer_approval_converts_application_to_student(client) -> None:
    """Officer approval should create the official student and transfer docs."""
    curriculum, semester = _career_program()
    applicant_user = User.objects.create_user("approve_applicant")
    _group_user(applicant_user, "Prospecting Student")
    application = EnrollmentApplication.objects.create(
        user=applicant_user,
        personal_email="approve@example.test",
        desired_curriculum=curriculum,
        desired_entry_semester=semester,
        academic_career=curriculum.academic_career,
        status=EnrollmentApplicationStatus.VERIFIED,
        email_verified_at=timezone.now(),
        documents_reviewed=True,
        placement_exam_completed=True,
        first_name="Approve",
        last_name="Applicant",
    )
    doc_type, _created = DocType.objects.get_or_create(
        code="waec",
        defaults={"label": "Waec"},
    )
    doc_status, _created = DocStatus.objects.get_or_create(
        code="approved",
        defaults={"label": "Approved"},
    )
    EnrollmentApplicationDoc.objects.create(
        application=application,
        document_type=doc_type,
        status=doc_status,
        data_file=SimpleUploadedFile("waec.pdf", b"pdf"),
    )
    officer = User.objects.create_user("approval_officer", password="PassW0rd!")
    _group_user(officer, "Enrollment Officer")
    officer.user_permissions.add(
        _perm("people", "view_enrollmentapplication"),
        _perm("people", "change_enrollmentapplication"),
    )
    client.force_login(officer)

    response = client.post(
        reverse("enrollment_application_detail", args=[application.id]),
        {"action": "approve"},
    )

    assert response.status_code == 302
    application.refresh_from_db()
    student = application.converted_student
    assert student is not None
    assert student.academic_career == AcademicCareer.GRADUATE
    assert student.primary_curriculum == curriculum
    assert applicant_user.groups.filter(name="Student").exists()
    assert not applicant_user.groups.filter(name="Prospecting Student").exists()
    assert DocStd.objects.filter(person=student, document_type=doc_type).exists()
