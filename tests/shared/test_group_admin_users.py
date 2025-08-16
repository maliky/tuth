"""Tests for the Group admin customization."""

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_group_admin_shows_users(client, superuser, user_factory, group_factory):
    """Group change page should display member usernames."""
    group = group_factory("Editors")
    user = user_factory("alice")
    group.user_set.add(user)

    client.force_login(superuser)
    url = reverse("admin:auth_group_change", args=[group.id])
    res = client.get(url)
    assert res.status_code == 200
    assert "alice" in res.content.decode()
