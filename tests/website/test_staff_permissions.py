"""Permission expectations for staff dashboards."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse


@pytest.mark.django_db
def test_registrar_officer_can_view_registrar_dashboard(client):
    User = get_user_model()
    user = User.objects.create_user("registrar_officer", password="PassW0rd!")
    officer_group, _ = Group.objects.get_or_create(name="Registrar Officer")
    user.groups.add(officer_group)

    client.force_login(user)
    response = client.get(reverse("staff_role_dashboard", args=["registrar"]))
    assert response.status_code == 200


@pytest.mark.django_db
def test_user_without_membership_blocked(client):
    User = get_user_model()
    user = User.objects.create_user("outsider", password="PassW0rd!")
    client.force_login(user)
    response = client.get(reverse("staff_role_dashboard", args=["registrar"]))
    assert response.status_code == 403
