"""Tests for timetable session model."""

import pytest
from django.db import IntegrityError, transaction

from app.timetable.models.section import Section
from app.timetable.models.session import Session

pytestmark = pytest.mark.django_db  # replace the @pytest.mark.django_db decorator


# ~~~~~~~~~~~~~~~~ DB Constraints ~~~~~~~~~~~~~~~~


def test_uniq_schedule_per_section(room, section, schedule):
    """In session, a (section, schedule) pair may appear at most once in Session rows.

    1. First insert ⟶ OK
    2. Second insert with the *same* pair ⟶ IntegrityError (DB-level)
    """
    # first row — should succeed
    Session.objects.create(room=room, section=section, schedule=schedule)

    with pytest.raises(IntegrityError):
        # use a sub-transaction so the IntegrityError does not abort the test DB
        with transaction.atomic():
            Session.objects.create(room=room, section=section, schedule=schedule)
