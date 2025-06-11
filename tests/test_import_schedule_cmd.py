"""Test import schedule cmd module."""

import io
import tempfile
import pytest
from django.core.management import call_command
from app.spaces.models import Location, Room
from app.timetable.models import Section, Session


@pytest.mark.django_db
def test_import_schedule_creates_schedule_and_space(tmp_path):
    csv = io.StringIO(
        "college,course_name,course_no,semester,section,location,weekday,time_start,time_end,instructor,curriculum\n"
        "COAS,MATH,101,24-25_Sem1,1,B2,Mon,08:00,09:00,Dr Foo,BSCS\n"
    )
    csv_path = tmp_path / "schedule.csv"
    csv_path.write_text(csv.getvalue())

    call_command("import_schedule", str(csv_path))

    section = Section.objects.get(course__code="MATH101")
    assert section.schedule == "Mon 08:00-09:00"

    sched = Session.objects.get()
    assert sched.weekday == 1
    assert sched.start_time.strftime("%H:%M") == "08:00"
    assert sched.end_time.strftime("%H:%M") == "09:00"

    assert Location.objects.filter(short_name="B2").exists()
    assert Room.objects.count() == 0
