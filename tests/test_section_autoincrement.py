import pytest
from datetime import date

from app.academics.models import College, Course
from app.timetable.models import AcademicYear, Semester, Section


@pytest.mark.django_db
def test_assigns_1_when_first_section_created():
    college = College.objects.create(code="COAS", fullname="Arts")
    course = Course.objects.create(
        name="MATH", number="101", title="Calculus", college=college
    )
    ay = AcademicYear.objects.create(start_date=date(2024, 8, 1))
    sem = Semester.objects.create(academic_year=ay, number=1)

    section = Section.objects.create(course=course, semester=sem, number=None)

    assert section.number == 1


@pytest.mark.django_db
def test_sequential_numbers():
    college = College.objects.create(code="COAS", fullname="Arts")
    course = Course.objects.create(
        name="MATH", number="101", title="Calculus", college=college
    )
    ay = AcademicYear.objects.create(start_date=date(2024, 8, 1))
    sem = Semester.objects.create(academic_year=ay, number=1)

    first = Section.objects.create(course=course, semester=sem, number=None)
    second = Section.objects.create(course=course, semester=sem, number=None)

    assert first.number == 1
    assert second.number == 2


@pytest.mark.django_db
def test_updating_existing_section_does_not_change_number():
    college = College.objects.create(code="COAS", fullname="Arts")
    course = Course.objects.create(
        name="MATH", number="101", title="Calculus", college=college
    )
    ay = AcademicYear.objects.create(start_date=date(2024, 8, 1))
    sem = Semester.objects.create(academic_year=ay, number=1)

    section = Section.objects.create(course=course, semester=sem, number=None)
    section.schedule = "MWF"
    section.save()
    section.refresh_from_db()

    assert section.number == 1
