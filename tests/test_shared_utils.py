import pytest
from datetime import date
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from types import SimpleNamespace

from app.academics.models import College, Curriculum
from app.shared.utils import validate_model_status


class DummyHistory:
    def __init__(self) -> None:
        self.entries: list[SimpleNamespace] = []

    def create(self, **kwargs):
        entry = SimpleNamespace(**kwargs)
        self.entries.insert(0, entry)
        return entry

    def first(self):
        return self.entries[0] if self.entries else None


@pytest.mark.django_db
def test_validate_model_status_valid():
    user = get_user_model().objects.create(username="john")
    college = College.objects.create(code="COAS", fullname="College of Arts and Sciences")
    curriculum = Curriculum.objects.create(
        college=college,
        title="Public Health",
        short_name="PH",
        creation_date=date.today(),
    )
    history = DummyHistory()
    curriculum._add_status = lambda state, author: history.create(state=state, author=author)  # type: ignore[assignment]
    curriculum.current_status = lambda: history.first()  # type: ignore[assignment]
    curriculum.set_pending(user)
    validate_model_status(curriculum)


@pytest.mark.django_db
def test_validate_model_status_invalid():
    user = get_user_model().objects.create(username="john")
    college = College.objects.create(code="COAS", fullname="College of Arts and Sciences")
    curriculum = Curriculum.objects.create(
        college=college,
        title="Nursing",
        short_name="NUR",
        creation_date=date.today(),
    )
    history = DummyHistory()
    curriculum._add_status = lambda state, author: history.create(state=state, author=author)  # type: ignore[assignment]
    curriculum.current_status = lambda: history.first()  # type: ignore[assignment]
    curriculum.set_rejected(user)
    with pytest.raises(ValidationError):
        validate_model_status(curriculum)


@pytest.mark.django_db
def test_validate_model_status_no_history():
    college = College.objects.create(code="COAS", fullname="College of Arts and Sciences")
    curriculum = Curriculum.objects.create(
        college=college,
        title="Environmental Studies",
        short_name="ES",
        creation_date=date.today(),
    )
    history = DummyHistory()
    curriculum._add_status = lambda state, author: history.create(state=state, author=author)  # type: ignore[assignment]
    curriculum.current_status = lambda: history.first()  # type: ignore[assignment]
    result = validate_model_status(curriculum)  # type: ignore[func-returns-value]
    assert result is None
