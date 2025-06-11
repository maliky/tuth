"""Test populate sections module."""

import io
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model

from app.spaces.models import Location, Room
from app.shared.management.populate_helpers.sections import populate_sections_from_csv
from app.timetable.models import Section


class DummyCmd:
    def __init__(self) -> None:
        class DummyStyle:
            def __getattr__(self, name):
                return lambda msg: msg

        self.style = DummyStyle()
        self.stdout = io.StringIO()


@pytest.mark.django_db
def test_populate_sections_strip_and_optional_fields():
    User = get_user_model()
    User.objects.create(id=2, username="inst")
    space = Location.objects.create(id=1, code="B1")
    Room.objects.create(id=1, name="101", space=space)

    csv = io.StringIO(
        """college,course,semester,number,instructor,room,max_seats\n"
        "COAS,MATH101,24-25_Sem1, 5 , 2 , 1 , 40\n"
        "COAS,MATH102,24-25_Sem1, , , , \n"
        """
    )

    cmd = DummyCmd()
    populate_sections_from_csv(cmd, csv)

    sec1 = Section.objects.get(course__code="MATH101")
    assert sec1.number == 5
    assert sec1.instructor_id == 2
    assert sec1.room_id == 1
    assert sec1.max_seats == 40

    sec2 = Section.objects.get(course__code="MATH102")
    assert sec2.number == 1
    assert sec2.instructor_id is None
    assert sec2.room_id is None
    assert sec2.max_seats == 30
