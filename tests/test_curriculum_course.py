from datetime import date

import pytest
from tablib import Dataset

from app.academics.admin.resources import CurriculumResource
from app.academics.models import College, Course, Curriculum, CurriculumCourse


@pytest.mark.django_db
def test_curriculum_import_sets_year_level():
    college = College.objects.create(code="COAS", fullname="College of Arts")
    Course.objects.create(name="BIO", number="101", title="Bio I", college=college)
    Course.objects.create(name="BIO", number="201", title="Bio II", college=college)

    data = Dataset(headers=["short_name", "title", "college", "list_courses"])
    data.append(["SCI", "Science", college.code, "BIO101;BIO201"])

    resource = CurriculumResource()
    result = resource.import_data(data, raise_errors=True)
    assert not result.has_errors()

    curriculum = Curriculum.objects.get(short_name="SCI")
    cc1 = CurriculumCourse.objects.get(curriculum=curriculum, course__number="101")
    cc2 = CurriculumCourse.objects.get(curriculum=curriculum, course__number="201")
    assert cc1.year_level == 1
    assert cc2.year_level == 2


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
