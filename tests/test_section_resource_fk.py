"tests/test_section_resource_fk.py"
import csv
from io import StringIO
from pathlib import Path

import pytest
from django.core import management
from django.db import IntegrityError
from import_export import results, resources
from tablib import Dataset

from app.timetable.admin.resources.section import SectionResource
from app.timetable.models import Section

# ------------------------------------------------------------------ helpers
def _dataset(course, semester, faculty="Jane Smith") -> Dataset:
    """
    Build the single‑row Dataset required by SectionResource.
    """
    ds = Dataset()
    ds.headers = [
        "academic_year",
        "course_name",
        "course_no",
        "faculty",
        "section_no",
        "semester_no",
    ]
    ds.append(
        (
            semester.academic_year.code,  # 25‑26
            course.name,                  # AGR
            str(course.number),           # 121
            faculty,                      # Jane Smith
            "1",                          # section_no
            str(semester.number),         # 1
        )
    )
    return ds


def _as_csv(tmp_path: Path, dataset: Dataset) -> Path:
    """
    Serialise *dataset* to a CSV file and return its path.
    """
    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow(dataset.headers)
    writer.writerows(dataset)
    file_path = tmp_path / "import.csv"
    file_path.write_text(buf.getvalue(), encoding="utf‑8")
    return file_path


# ------------------------------------------------------------------ tests
@pytest.mark.django_db
def test_double_import_with_same_resource_raises_fk(course, semester):
    """
    Same resource → dry‑run then real run ⇒ orphan FacultyProfile cached ⇒ FK error.
    """
    ds = _dataset(course, semester)
    res = SectionResource()

    # first pass (validation only) should be clean
    dry = res.import_data(ds, dry_run=True)
    assert not dry.has_errors()

    # second pass re‑uses the cached FacultyProfile and breaks FK
    with pytest.raises(IntegrityError):
        res.import_data(ds, dry_run=False)


@pytest.mark.django_db
def test_double_import_with_new_resource_is_safe(course, semester):
    """
    The bug disappears when a *new* SectionResource is instantiated
    for the real import – this is the recommended workaround/fix.
    """
    ds = _dataset(course, semester)

    SectionResource().import_data(ds, dry_run=True)   # validation
    real = SectionResource().import_data(ds, dry_run=False)

    assert isinstance(real, results.Result)
    assert not real.has_errors()
    assert Section.objects.filter(
        course=course, semester=semester, number=1
    ).exists()


@pytest.mark.django_db
def test_management_command_reports_failure(tmp_path, course, semester, capsys):
    """
    Run the *import_resources* command against a CSV that should fail and
    make sure the error string reaches stdout/stderr.
    """
    csv_path = _as_csv(tmp_path, _dataset(course, semester))
    # only SectionResource is executed by the command, so the bug is triggered
    management.call_command("import_resources", "-f", str(csv_path))

    captured = capsys.readouterr()
    assert "Section import failed" in captured.out
