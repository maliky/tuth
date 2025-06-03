<<<<<<< HEAD
# tests/test_section_widgets.py
from __future__ import annotations
=======
"""Test section widgets module."""
>>>>>>> github/codo/add-missing-module-level-docstrings

import pytest

from app.timetable.admin.widgets import SectionCodeWidget
from app.timetable.models import Semester


@pytest.mark.django_db
def test_section_code_widget_parses_semester() -> None:
    widget: SectionCodeWidget = SectionCodeWidget()

    semester: Semester
    number: int
    semester, number = widget.clean("24-25_Sem1:2")

    assert semester.academic_year.short_name == "24-25"
    assert semester.number == 1
    assert number == 2
