import pytest
from django.contrib.auth.models import User

from app.people.utils import mk_username


def test_mk_username_default():
    """Default username generation without uniqueness."""
    assert mk_username("Isaac", "Yancy") == "iyancy"


@pytest.mark.django_db
def test_mk_username_unique_appends_numbers():
    """Unique usernames append incremental numbers when needed."""
    User.objects.create_user(username="iyancy")
    User.objects.create_user(username="iyancy2")

    assert mk_username("Isaac", "Yancy", unique=True) == "iyancy3"
