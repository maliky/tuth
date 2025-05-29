import pytest
from tablib import Dataset
from app.academics.admin.resources import CurriculumResource
from app.academics.models import College, Course, CurriculumCourse, Curriculum


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
