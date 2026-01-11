"""Tests for the import_resources SecSession path."""

from __future__ import annotations

from django.core.management import call_command
import pytest
from tablib import Dataset

from app.timetable.admin.session_resources import SecSessionResource
from app.timetable.models.session import SecSession
from app.timetable.choices import WEEKDAYS_NUMBER


@pytest.mark.django_db
def test_secsession_resource_import_data() -> None:
    """Import a SecSession row directly through the resource."""
    dataset = Dataset(
        headers=[
            "room",
            "space",
            "weekday",
            "start_time",
            "end_time",
            "section_no",
            "curriculum",
            "course_no",
            "dept_code",
            "college_code",
            "faculty",
            "semester_no",
            "academic_year",
            "course_title",
            "credit_hours",
        ]
    )
    dataset.append(
        [
            "201",
            "NB",
            "Monday",
            "08:30",
            "09:45",
            "1",
            "BACC",
            "101",
            "ACCT",
            "COAS",
            "Dylan, John A",
            "2",
            "25-26",
            "Accounting 101",
            "3",
        ]
    )

    resource = SecSessionResource()
    result = resource.import_data(dataset, dry_run=False, raise_errors=True)

    assert not result.has_errors()
    assert SecSession.objects.count() == 1, f"{SecSession.objects.all()}"
    session = SecSession.objects.select_related("schedule", "room", "section").get()
    assert session.section.number == 1, f"{session}"
    assert session.room.code == "201", f"{session}"
    assert session.room.space.code == "NB", f"{session}"
    assert session.schedule is not None, f"{session}"
    assert session.schedule.weekday == WEEKDAYS_NUMBER.MONDAY, f"{session}"


@pytest.mark.django_db
def test_import_resources_secsession(tmp_path) -> None:
    """Import a SecSession row via import_resources."""
    tsv_data = (
        "room\tspace\tweekday\tstart_time\tend_time\tsection_no\tcurriculum\t"
        "course_no\tdept_code\tcollege_code\tfaculty\tsemester_no\tacademic_year\t"
        "course_title\tcredit_hours\n"
        "201\tNB\tMonday\t08:30\t09:45\t1\tBACC\t101\tACCT\tCOAS\t"
        "Dylan, John A\t2\t25-26\tAccounting 101\t3\n"
    )
    path = tmp_path / "secsession.tsv"
    path.write_text(tsv_data, encoding="utf-8")

    call_command("import_resources", "-f", str(path), "-r", "SecSession")

    assert SecSession.objects.count() == 1
    session = SecSession.objects.select_related("schedule", "room", "section").get()
    assert session.section.number == 1
    assert session.room.code == "201"
    assert session.room.space.code == "NB"
    assert session.schedule is not None
    assert session.schedule.weekday == WEEKDAYS_NUMBER.MONDAY
