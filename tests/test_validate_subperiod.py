"""Test validate_subperiod helper."""

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError

from app.timetable.models import Term
from app.timetable.utils import validate_subperiod


@pytest.mark.django_db
def test_validate_subperiod_overlap(semester):
    Term.objects.create(
        semester=semester,
        number=1,
        start_date=semester.start_date,
        end_date=semester.start_date + timedelta(days=30),
    )

    with pytest.raises(ValidationError):
        validate_subperiod(
            sub_start=semester.start_date + timedelta(days=15),
            sub_end=semester.start_date + timedelta(days=45),
            container_start=semester.start_date,
            container_end=semester.end_date,
            overlap_qs=Term.objects.filter(semester=semester),
            overlap_message="overlap",
            label="term",
        )


@pytest.mark.django_db
def test_validate_subperiod_out_of_range(semester):
    with pytest.raises(ValidationError):
        validate_subperiod(
            sub_start=semester.start_date - timedelta(days=1),
            sub_end=semester.start_date + timedelta(days=5),
            container_start=semester.start_date,
            container_end=semester.end_date,
            label="term",
        )
