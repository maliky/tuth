"""Permission expectations for staff dashboards."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.urls import reverse

from app.registry.models.registration import Registration


def _perm(app_label: str, codename: str) -> Permission:
    """Return a concrete model permission scoped by app label."""
    return Permission.objects.get(
        content_type__app_label=app_label,
        codename=codename,
    )


@pytest.mark.django_db
def test_reg_officer_can_view_reg_dashboard(client):
    User = get_user_model()
    user = User.objects.create_user("reg_officer", password="PassW0rd!")
    officer_group, _ = Group.objects.get_or_create(name="Registrar Officer")
    user.groups.add(officer_group)

    client.force_login(user)
    response = client.get(reverse("staff_role_dashboard", args=["registrar"]))
    assert response.status_code == 200
    assert "Authorized database" not in response.content.decode()


@pytest.mark.django_db
def test_faculty_dashboard_uses_sidebar_without_duplicate_action_panel(client):
    """Faculty grade entry should live in the sidebar, not duplicated as a card."""
    User = get_user_model()
    user = User.objects.create_user("faculty_no_dupe", password="PassW0rd!")
    instructor_group, _ = Group.objects.get_or_create(name="Instructor")
    user.groups.add(instructor_group)

    client.force_login(user)
    response = client.get(reverse("staff_role_dashboard", args=["faculty"]))
    content = response.content.decode()

    assert response.status_code == 200
    assert reverse("faculty_grade_sections") in content
    assert "What can I do here?" not in content


@pytest.mark.django_db
def test_finance_officer_dashboard_dedupes_sidebar_actions(client):
    """Finance console links should not appear both in sidebar and action cards."""
    User = get_user_model()
    user = User.objects.create_user("finance_no_dupe", password="PassW0rd!")
    finance_group, _ = Group.objects.get_or_create(name="Finance Officer")
    user.groups.add(finance_group)

    client.force_login(user)
    response = client.get(reverse("staff_role_dashboard", args=["finance_officer"]))
    content = response.content.decode()

    assert response.status_code == 200
    assert reverse("finance_officer_invoices") in content
    assert "Open finance console" not in content
    assert "What can I do here?" not in content


@pytest.mark.django_db
def test_reg_officer_dashboard_shows_authorized_admin_shortcuts(client):
    """Registrar officer dashboard should expose only permitted admin tables."""
    User = get_user_model()
    user = User.objects.create_user(
        "reg_officer_admin",
        password="PassW0rd!",
        is_staff=True,
    )
    officer_group, _ = Group.objects.get_or_create(name="Registrar Officer")
    user.groups.add(officer_group)
    user.user_permissions.add(
        _perm("people", "view_student"),
        _perm("registry", "view_registration"),
    )

    client.force_login(user)
    response = client.get(reverse("staff_role_dashboard", args=["reg_officer"]))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Authorized database" in content
    assert reverse("admin:people_student_changelist") in content
    assert reverse("admin:registry_registration_changelist") in content
    assert reverse("admin:registry_grade_changelist") not in content


@pytest.mark.django_db
def test_registrar_dashboard_scopes_pending_payment_metric(
    client,
    reg_sem_pair_factory,
    reg_sec_factory,
    reg_std_factory,
):
    """Registrar metric should show current-term pending payment, not all history."""
    User = get_user_model()
    user = User.objects.create_user("reg_metric", password="PassW0rd!")
    officer_group, _ = Group.objects.get_or_create(name="Registrar Officer")
    user.groups.add(officer_group)
    _academic_year, previous, current = reg_sem_pair_factory()
    previous_section, curriculum = reg_sec_factory(
        previous,
        course_number="410",
        curriculum_short_name="CURRI_REG_METRIC",
    )
    current_section, _curriculum = reg_sec_factory(
        current,
        course_number="411",
        curriculum_short_name="CURRI_REG_METRIC",
    )
    previous_student = reg_std_factory("reg_metric_previous", curriculum, previous)
    current_student = reg_std_factory("reg_metric_current", curriculum, current)
    Registration.objects.create(student=previous_student, section=previous_section)
    Registration.objects.create(student=current_student, section=current_section)

    client.force_login(user)
    response = client.get(reverse("staff_role_dashboard", args=["registrar"]))
    metrics = response.context["metrics"]
    pending_metric = next(
        metric
        for metric in metrics
        if str(metric["label"]).startswith("Registrations pending payment")
    )

    assert response.status_code == 200
    assert pending_metric["label"] == "Registrations pending payment (current term)"
    assert pending_metric["value"] == 1
    assert "Registrations pending clearance" not in response.content.decode()


@pytest.mark.django_db
def test_user_without_membership_blocked(client):
    User = get_user_model()
    user = User.objects.create_user("outsider", password="PassW0rd!")
    client.force_login(user)
    response = client.get(reverse("staff_role_dashboard", args=["registrar"]))
    assert response.status_code == 403
