import pytest

from app.timetable.admin import SectionCodeWidget
from app.timetable.models import Semester


@pytest.mark.django_db
def test_section_code_widget_parses_semester_and_number():
    scw = SectionCodeWidget()

    semester, num = scw.clean("24-25_Sem1:2")

    assert isinstance(semester, Semester)
    assert semester.academic_year.short_name == "24-25"
    assert semester.number == 1
    assert num == 2
