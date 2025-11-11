"""Tests for timetable session model."""

import pytest
from django.db import IntegrityError, transaction

from app.timetable.models.session import SecSession

pytestmark = pytest.mark.django_db  # replace the @pytest.mark.django_db decorator


# ~~~~~~~~~~~~~~~~ DB Constraints ~~~~~~~~~~~~~~~~


def test_uniq_schedule_per_section(room, section, schedule):
    """In session, a (section, schedule) pair may appear at most once in SecSession rows.

    1. First insert ⟶ OK
    2. Second insert with the *same* pair ⟶ IntegrityError (DB-level)
    """
    # first row — should succeed
    SecSession.objects.create(room=room, section=section, schedule=schedule)

    with pytest.raises(IntegrityError):
        # use a sub-transaction so the IntegrityError does not abort the test DB
        with transaction.atomic():
            SecSession.objects.create(room=room, section=section, schedule=schedule)
