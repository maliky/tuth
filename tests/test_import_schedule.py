"""Test import schedule module."""

import io
import pytest
from django.core.management import call_command
from app.timetable.models import Section, Schedule, Semester
from app.academics.models import College


@pytest.mark.django_db
def test_import_schedule_creates_section(tmp_path):
    csv = io.StringIO(
        "college,course_code,course_no,semester,section,location,instructor,curriculum,weekday,time_start,time_end,sts,ets\n"
        "COAS,MATH,101,24-25_Sem1,1,B1-101,John Doe,BSCS,Mon,08:00,09:00,2024-09-01,2024-09-30\n"
    )
    path = tmp_path / "sched.csv"
    path.write_text(csv.getvalue())

    call_command("import_schedule", str(path))

    section = Section.objects.get()
    schedule = Schedule.objects.get()

    assert section.schedule == schedule
    assert section.start_date.isoformat() == "2024-09-01"
    assert section.end_date.isoformat() == "2024-09-30"
