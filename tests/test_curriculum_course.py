import pytest
from datetime import date

from app.academics.models import College, Course, Curriculum, CurriculumCourse


@pytest.mark.django_db
def test_year_level_defaults_from_course_number():
    college = College.objects.create(
        code="COET",
        fullname="College of Engineering and Technology",
    )
    curriculum = Curriculum.objects.create(
        title="Engineering",
        short_name="ENGR",
        college=college,
        creation_date=date.today(),
    )
    course = Course.objects.create(
        name="CSC",
        number="201",
        title="Intro",
        college=college,
    )

    cc, created = CurriculumCourse.objects.get_or_create(
        curriculum=curriculum,
        course=course,
    )

    assert created
    assert cc.year_level == 2
