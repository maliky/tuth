import pytest
from django.contrib.auth import get_user_model
from django.db import connection, models

from django.db.models.signals import post_save

from app.shared.mixins import StatusHistory, StatusableMixin
from app.academics.signals import sync_curriculum_is_active
from app.people.models.profiles import UserDelegateMixin

User = get_user_model()


class DummyStatus(StatusableMixin, models.Model):
    """Minimal model for StatusableMixin tests."""

    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        app_label = "tests"


class DummyDelegate(UserDelegateMixin, models.Model):
    """Minimal model for UserDelegateMixin tests."""

    user = models.OneToOneField(User, on_delete=models.CASCADE)

    class Meta:
        app_label = "tests"


@pytest.fixture(autouse=True)
def disconnect_signals():
    """Disable curriculum sync signal during tests."""
    post_save.disconnect(sync_curriculum_is_active, sender=StatusHistory)
    try:
        yield
    finally:
        post_save.connect(sync_curriculum_is_active, sender=StatusHistory)


@pytest.fixture(autouse=True)
@pytest.mark.django_db(transaction=True)
def setup_models():
    """Create test tables for dummy models."""
    with connection.schema_editor() as editor:
        editor.create_model(StatusHistory)
        editor.create_model(DummyStatus)
        editor.create_model(DummyDelegate)
    try:
        yield
    finally:
        with connection.schema_editor() as editor:
            editor.delete_model(DummyStatus)
            editor.delete_model(DummyDelegate)
            editor.delete_model(StatusHistory)


@pytest.mark.django_db(transaction=True)
def test_add_status_appends_history():
    user = User.objects.create_user(username="u")
    obj = DummyStatus.objects.create(user=user)  # type: ignore[attr-defined]

    assert obj.status_history.count() == 0
    entry = obj._add_status("pending", user)

    assert obj.status_history.count() == 1
    assert entry.status == "pending"
    assert obj.status_history.first() == entry


@pytest.mark.django_db(transaction=True)
def test_user_delegate_get_set():
    user = User.objects.create_user(username="u", first_name="Old")
    delegate = DummyDelegate.objects.create(user=user)  # type: ignore[attr-defined]

    # __getattr__ forwards to user
    assert delegate.first_name == "Old"

    # __setattr__ updates user
    delegate.first_name = "New"
    assert delegate.user.first_name == "New"
    assert delegate.first_name == "New"
