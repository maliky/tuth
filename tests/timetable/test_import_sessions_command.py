"""Tests for the import_sessions command."""

from __future__ import annotations

from django.core.management import call_command
import pytest

from app.timetable.models.session import SecSession
from app.timetable.choices import WEEKDAYS_NUMBER


@pytest.mark.django_db
def test_import_sessions_command_creates_session(tmp_path) -> None:
    """Import a SecSession row using the import_sessions command."""
    tsv_data = (
        "academic_year\tsemester_no\tcollege_code\tdept_code\tcourse_no\t"
        "course_title\tcurriculum\tcredit\tsection_no\tweekday\tstart_time\t"
        "end_time\tspace\troom\tfaculty\n"
        "25-26\t2\tCAS\tACCT\t101\tAccounting 101\tBACC\t3\t1\t"
        "Monday\t08:30\t09:45\tNB\t201\tDylan, John A\n"
    )
    path = tmp_path / "sessions.tsv"
    path.write_text(tsv_data, encoding="utf-8")

    call_command("import_sessions", "--file", str(path), "--semester-code", "25-26s2")

    assert SecSession.objects.count() == 1
    session = SecSession.objects.select_related("schedule", "room", "section").get()
    assert session.section.number == 1
    assert session.room.code == "201"
    assert session.room.space.code == "NB"
    assert session.schedule is not None
    assert session.schedule.weekday == WEEKDAYS_NUMBER.MONDAY
