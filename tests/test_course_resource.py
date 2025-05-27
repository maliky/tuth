import tablib
import pytest

from app.academics.admin.resources import CourseResource
from app.academics.models import College, Course


@pytest.mark.django_db
def test_course_import_without_name_number():
    College.objects.create(code="COAS", fullname="Arts")
    dataset = tablib.Dataset(
        headers=["code", "title", "year", "college", "name", "number"]
    )
    dataset.append(["MATH101", "Calculus", "1", "COAS", "", ""])
    resource = CourseResource()
    resource.import_data(dataset, raise_errors=True)
    course = Course.objects.get(code="MATH101")
    assert course.title == "Calculus"
    assert resource._mismatched_rows == []


@pytest.mark.django_db
def test_course_import_skips_mismatched_rows():
    College.objects.create(code="COAS", fullname="Arts")
    dataset = tablib.Dataset(headers=["code", "name", "number", "title", "college"])
    dataset.append(["MATH101", "MATH", "101", "Calc I", "COAS"])
    dataset.append(["ENG101", "ENG", "201", "Eng", "COAS"])
    resource = CourseResource()
    resource.import_data(dataset, raise_errors=True)
    assert Course.objects.filter(code="MATH101").exists()
    assert not Course.objects.filter(code="ENG101").exists()
    assert len(resource._mismatched_rows) == 1
