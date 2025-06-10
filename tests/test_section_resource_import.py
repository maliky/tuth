"""Test section resource import module."""

import pytest
from tablib import Dataset

from app.timetable.admin.resources.section import SectionResource
from app.timetable.models import Section


@pytest.mark.django_db
def test_import_section_success():
    """Importing valid data creates a Section."""
    data = Dataset(
        headers=[
            "academic_year",
            "semester_no",
            "course_code",
            "course_no",
            "college",
            "section_no",
            "faculty",
        ]
    )
    data.append(["24-25", "1", "MATH", "101", "COAS", "1", "Dr Jane Doe"])

    resource = SectionResource()
    result = resource.import_data(data, dry_run=False)

    assert not result.has_errors()
    section = Section.objects.get()
    assert section.number == 1
    assert section.course.code == "MATH101"
    assert section.semester.number == 1
    assert section.semester.academic_year.code == "24-25"
    assert section.faculty.user.first_name == "Jane"


@pytest.mark.django_db
def test_import_section_missing_number_reports_error():
    """Missing required fields should raise validation errors."""
    data = Dataset(
        headers=[
            "academic_year",
            "semester_no",
            "course_code",
            "course_no",
            "college_code",
            "section_no",
            "faculty",
        ]
    )
    # blank section_no triggers validation failure
    data.append(["24-25", "1", "MATH", "101", "COAS", "", "Dr Jane Doe"])

    resource = SectionResource()
    result = resource.import_data(data, dry_run=False)

    assert result.has_errors()
    assert Section.objects.count() == 0
