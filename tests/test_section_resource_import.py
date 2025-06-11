# tests/test_section_resource_import.py

import pytest
from django.core.exceptions import ValidationError
from import_export import results
from tablib import Dataset

from app.timetable.admin.resources.section import SectionResource
from app.timetable.models import Section


def make_dataset(headers, rows):
    ds = Dataset()
    ds.headers = list(headers)
    for row in rows:
        ds.append(tuple(row.get(h, "") for h in headers))
    return ds


@pytest.mark.parametrize(
    "missing", ["academic_year", "semester_no", "course_name", "section_no", "faculty"]
)
@pytest.mark.django_db
def test_missing_required_header_triggers_error(missing, course, semester):
    """
    If any of the five required columns is absent, import_data(dry_run=True)
    must report errors.
    """
    headers = ["academic_year", "semester_no", "course_name", "section_no", "faculty"]
    headers.remove(missing)
    row = { "academic_year": semester.academic_year.code,
            "semester_no": str(semester.number), "course_name":
            course.code, "section_no": "1", "faculty": "John Doe", }
    ds = make_dataset(headers, [row])
    res = SectionResource()
    # strip blank headers if any
    res.before_import(ds, using_transactions=False, dry_run=True)
    result = res.import_data(ds, dry_run=True)
    assert result.has_errors(), f"Expected errors when '{missing}' is missing"


@pytest.mark.django_db
def test_successful_import_creates_section(course, semester):
    """
    A well-formed row with all five required columns imports cleanly
    and creates a Section.
    """
    headers = ["academic_year", "semester_no", "course_name", "section_no", "faculty"]
    row = {
        "academic_year": semester.academic_year.code,
        "semester_no": str(semester.number),
        "course_name": course.code,
        "section_no": "1",
        "faculty": "Jane Smith",
    }
    ds = make_dataset(headers, [row])
    res = SectionResource()
    # dry_run should pass
    dry = res.import_data(ds, dry_run=True)
    
    assert not dry.has_errors()
        
    # real import
    imp = res.import_data(ds, dry_run=False)
    assert isinstance(imp, results.ImportResult)
    # verify Section exists
    assert Section.objects.filter(course=course, semester=semester, number=1).exists()


# @pytest.mark.django_db
# def test_import_section_2_without_1_fails(course, semester):
#     headers = ["academic_year", "semester_no", "course_name", "section_no", "faculty"]
#     row = {
#         "academic_year": semester.academic_year.code,
#         "semester_no": str(semester.number),
#         "course_name": course.code,
#         "section_no": "2",
#         "faculty": "jane",
#     }
#     ds = make_dataset(headers, [row])
#     res = SectionResource()
#     with pytest.raises(ValidationError):
#         # during before_import_row
#         res.before_import_row(ds.dict[0], dry_run=True)
#     # or via import_data
#     result = res.import_data(ds, dry_run=True)
#     assert result.has_errors()
#     assert "Cannot create section 2 without prior section 1" in str(
#         result.row_errors()[0][1][0]
#     )

