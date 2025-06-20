from app.academics.admin.widgets import CourseWidget
import pytest

from django.db import IntegrityError
from app.academics.models import College, Course
from app.shared.enums import CREDIT_NUMBER


@pytest.mark.django_db
def test_course_widget_returns_existing_course():
    col = College.objects.create(code="COAS", fullname="College of Arts")
    course = Course.objects.create(name="MATH", number="101", title="Math", college=col)
    cw = CourseWidget(model=Course, field="code")

    result = cw.clean("MATH101 - COAS", {"college": "COAS"})

    assert result == course
    assert College.objects.count() == 1
    assert Course.objects.count() == 1


@pytest.mark.django_db
def test_course_widget_creates_missing_course_and_college():
    cw = CourseWidget(model=Course, field="code")

    course = cw.clean("PHY102 - COET", {"college": "COET"})

    college = College.objects.get(code="COET")
    assert course.college == college
    assert course.title == "PHY102 - COET"
    assert course.credit_hours == CREDIT_NUMBER.THREE


@pytest.mark.django_db
def test_course_widget_defaults_to_row_college():
    col = College.objects.create(code="COAS", fullname="College of Arts")
    cw = CourseWidget(model=Course, field="code")

    course = cw.clean("CHEM100", {"college": "COAS"})

    assert course.college == col
    assert course.title == "CHEM100"
    assert College.objects.filter(code="COAS").count() == 1


@pytest.mark.django_db
def test_course_widget_raises_value_error_with_multiple_matches():
    col = College.objects.create(code="COAS", fullname="College of Arts")
    Course.objects.create(name="BIO", number="101", title="Bio I", college=col)

    with pytest.raises(IntegrityError):
        Course.objects.create(name="BIO", number="101", title="Bio II", college=col)

    cw = CourseWidget(model=Course, field="code")

    with pytest.raises(ValueError):
        cw.clean("BIO101 - COAS", {"college": "COAS"})


@pytest.mark.django_db
def test_course_widget_token_college_overrides_row_college():
    row_college = College.objects.create(code="COAS", fullname="College of Arts")
    token_college = College.objects.create(code="COET", fullname="College of Engineering")
    course = Course.objects.create(
        name="MATH", number="101", title="Math", college=token_college
    )
    cw = CourseWidget(model=Course, field="code")

    result = cw.clean("MATH101 - COET", {"college": row_college.code})

    assert result == course
    assert result.college == token_college


@pytest.mark.django_db
def test_college_widget_tracks_new_colleges():
    cw = CollegeWidget(College, "code")
    dummy = SimpleNamespace(_new_colleges=set())
    cw._resource = dummy

    obj = cw.clean("COET")

    assert obj.code == "COET"
    assert "COET" in dummy._new_colleges


@pytest.mark.django_db
def test_college_widget_skips_existing_colleges():
    College.objects.create(code="COAS", fullname="Arts")
    cw = CollegeWidget(College, "code")
    dummy = SimpleNamespace(_new_colleges=set())
    cw._resource = dummy

    obj = cw.clean("COAS")

    assert obj.code == "COAS"
    assert not dummy._new_colleges
