"""Permission expectations for staff dashboards."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.urls import reverse


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
def test_user_without_membership_blocked(client):
    User = get_user_model()
    user = User.objects.create_user("outsider", password="PassW0rd!")
    client.force_login(user)
    response = client.get(reverse("staff_role_dashboard", args=["registrar"]))
    assert response.status_code == 403
