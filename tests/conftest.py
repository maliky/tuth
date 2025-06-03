"""Conftest module."""

import pytest
from django.contrib.auth import get_user_model


@pytest.fixture
def superuser(db):
    User = get_user_model()
    return User.objects.create_superuser(
        username="super", email="super@example.com", password="secret123"
    )
