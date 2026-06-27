"""Tests for registrar registration correction pages."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse

from app.finance.models.invoice import CrsInvoice
from app.finance.models.status_types_methods import InvoiceStatus
from app.registry.models.grade import Grade
from app.registry.models.registration import Registration

pytestmark = pytest.mark.django_db


def _perm(app_label: str, codename: str) -> Permission:
    """Return a concrete model permission scoped by app label."""
    return Permission.objects.get(
        content_type__app_label=app_label,
        codename=codename,
    )


def _grant_registration_editor_perms(user, *actions: str) -> None:
    """Grant selected registration permissions to a registrar test user."""
    user.user_permissions.add(_perm("registry", "view_registration"))
    for action in actions:
        user.user_permissions.add(_perm("registry", f"{action}_registration"))


def test_dashboard_shows_registration_editor_for_authorized_registrar(
    client,
    reg_user_factory,
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
) -> None:
    """Registrar dashboard should link to student-semester registration correction."""
    user = reg_user_factory("registrar_registration_link")
    _grant_registration_editor_perms(user, "change")
    _academic_year, _previous, current = reg_sem_pair_factory()
    section, curriculum = reg_sec_factory(
        current,
        course_number="401",
        curriculum_short_name="CURRI_REGIO_LINK",
    )
    student = reg_std_factory("registrar_registration_link_student", curriculum, current)
    Registration.objects.create(student=student, section=section)

    client.force_login(user)
    response = client.get(
        reverse("reg_grades_dashboard"),
        {"student_id": str(student.id), "semester": str(current.id)},
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert "Correct registrations" in content
    assert (
        reverse("reg_registration_semester_editor", args=[student.id, current.id])
        in content
    )


def test_registration_editor_get_lists_student_semester_rows(
    client,
    reg_user_factory,
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
) -> None:
    """Opening the editor should show existing registrations without mutating."""
    user = reg_user_factory("registrar_registration_get")
    _grant_registration_editor_perms(user)
    _academic_year, _previous, current = reg_sem_pair_factory()
    section, curriculum = reg_sec_factory(
        current,
        course_number="402",
        curriculum_short_name="CURRI_REGIO_GET",
    )
    student = reg_std_factory("registrar_registration_get_student", curriculum, current)
    Registration.objects.create(student=student, section=section)

    client.force_login(user)
    response = client.get(
        reverse("reg_registration_semester_editor", args=[student.id, current.id])
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert "Official registration correction" in content
    assert (
        response.context["registration_rows"][0]["registration"].section_id == section.id
    )
    assert Registration.objects.filter(student=student, section=section).count() == 1


def test_registration_editor_adds_same_semester_registration(
    client,
    reg_user_factory,
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
) -> None:
    """Authorized registrar users can add one registration by section id."""
    user = reg_user_factory("registrar_registration_add")
    _grant_registration_editor_perms(user, "add")
    _academic_year, _previous, current = reg_sem_pair_factory()
    section, curriculum = reg_sec_factory(
        current,
        course_number="403",
        curriculum_short_name="CURRI_REGIO_ADD",
    )
    student = reg_std_factory("registrar_registration_add_student", curriculum, current)

    client.force_login(user)
    response = client.post(
        reverse("reg_registration_semester_editor", args=[student.id, current.id]),
        {"action": "add_registration", "section_id": str(section.id)},
    )

    registration = Registration.objects.get(student=student, section=section)
    assert response.status_code == 302
    assert registration.status_id == "pending"


def test_registration_editor_moves_clean_pending_registration(
    client,
    reg_user_factory,
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
) -> None:
    """A clean pending registration can move to another section in the same semester."""
    user = reg_user_factory("registrar_registration_move")
    _grant_registration_editor_perms(user, "change")
    _academic_year, _previous, current = reg_sem_pair_factory()
    old_section, curriculum = reg_sec_factory(
        current,
        course_number="404",
        curriculum_short_name="CURRI_REGIO_MOVE",
    )
    new_section, _curriculum = reg_sec_factory(
        current,
        course_number="405",
        curriculum_short_name="CURRI_REGIO_MOVE",
    )
    student = reg_std_factory("registrar_registration_move_student", curriculum, current)
    registration = Registration.objects.create(student=student, section=old_section)

    client.force_login(user)
    response = client.post(
        reverse("reg_registration_semester_editor", args=[student.id, current.id]),
        {
            "action": "move_registration",
            "registration_id": str(registration.id),
            "section_id": str(new_section.id),
        },
    )

    registration.refresh_from_db()
    assert response.status_code == 302
    assert registration.section_id == new_section.id


def test_registration_editor_rejects_cross_semester_move(
    client,
    reg_user_factory,
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
) -> None:
    """Registrar moves must stay within the selected semester."""
    user = reg_user_factory("registrar_registration_cross_sem")
    _grant_registration_editor_perms(user, "change")
    _academic_year, previous, current = reg_sem_pair_factory()
    old_section, curriculum = reg_sec_factory(
        current,
        course_number="406",
        curriculum_short_name="CURRI_REGIO_CROSS",
    )
    other_section, _curriculum = reg_sec_factory(
        previous,
        course_number="407",
        curriculum_short_name="CURRI_REGIO_CROSS",
    )
    student = reg_std_factory("registrar_registration_cross_student", curriculum, current)
    registration = Registration.objects.create(student=student, section=old_section)

    client.force_login(user)
    response = client.post(
        reverse("reg_registration_semester_editor", args=[student.id, current.id]),
        {
            "action": "move_registration",
            "registration_id": str(registration.id),
            "section_id": str(other_section.id),
        },
    )

    registration.refresh_from_db()
    assert response.status_code == 400
    assert registration.section_id == old_section.id


def test_registration_editor_deletes_clean_pending_registration(
    client,
    reg_user_factory,
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
) -> None:
    """Registrar delete is allowed only for clean pending rows."""
    user = reg_user_factory("registrar_registration_delete")
    _grant_registration_editor_perms(user, "delete")
    _academic_year, _previous, current = reg_sem_pair_factory()
    section, curriculum = reg_sec_factory(
        current,
        course_number="408",
        curriculum_short_name="CURRI_REGIO_DELETE",
    )
    student = reg_std_factory(
        "registrar_registration_delete_student", curriculum, current
    )
    registration = Registration.objects.create(student=student, section=section)

    client.force_login(user)
    response = client.post(
        reverse("reg_registration_semester_editor", args=[student.id, current.id]),
        {"action": "delete_registration", "registration_id": str(registration.id)},
    )

    assert response.status_code == 302
    assert not Registration.objects.filter(pk=registration.pk).exists()


def test_registration_editor_blocks_delete_when_grade_exists(
    client,
    reg_user_factory,
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
    reg_grade_factory,
) -> None:
    """Registrations tied to grades must not be deleted from the crude editor."""
    user = reg_user_factory("registrar_registration_delete_grade")
    _grant_registration_editor_perms(user, "delete")
    _academic_year, _previous, current = reg_sem_pair_factory()
    section, curriculum = reg_sec_factory(
        current,
        course_number="409",
        curriculum_short_name="CURRI_REGIO_GRADE",
    )
    student = reg_std_factory("registrar_registration_grade_student", curriculum, current)
    registration = Registration.objects.create(student=student, section=section)
    reg_grade_factory(student, section)

    client.force_login(user)
    response = client.post(
        reverse("reg_registration_semester_editor", args=[student.id, current.id]),
        {"action": "delete_registration", "registration_id": str(registration.id)},
    )

    assert response.status_code == 400
    assert Registration.objects.filter(pk=registration.pk).exists()
    assert Grade.objects.filter(student=student, section=section).exists()


def test_registration_editor_blocks_move_when_invoice_exists(
    client,
    reg_user_factory,
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
) -> None:
    """Registrations tied to finance rows must not be moved in the portal."""
    InvoiceStatus._populate_attributes_and_db()
    user = reg_user_factory("registrar_registration_invoice")
    _grant_registration_editor_perms(user, "change")
    _academic_year, _previous, current = reg_sem_pair_factory()
    old_section, curriculum = reg_sec_factory(
        current,
        course_number="410",
        curriculum_short_name="CURRI_REGIO_INVOICE",
    )
    new_section, _curriculum = reg_sec_factory(
        current,
        course_number="411",
        curriculum_short_name="CURRI_REGIO_INVOICE",
    )
    student = reg_std_factory(
        "registrar_registration_invoice_student", curriculum, current
    )
    registration = Registration.objects.create(student=student, section=old_section)
    CrsInvoice.objects.create(
        student=student,
        curriculum_course=old_section.curriculum_course,
        semester=current,
        initial_amount_due=Decimal("10.00"),
        balance=Decimal("10.00"),
    )

    client.force_login(user)
    response = client.post(
        reverse("reg_registration_semester_editor", args=[student.id, current.id]),
        {
            "action": "move_registration",
            "registration_id": str(registration.id),
            "section_id": str(new_section.id),
        },
    )

    registration.refresh_from_db()
    assert response.status_code == 400
    assert registration.section_id == old_section.id
