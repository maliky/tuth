"""Test CurriculumCourse.effective_credit_hours."""

import pytest

from app.academics.models import Curriculum, CurriculumCourse


@pytest.mark.django_db
def test_effective_credit_hours_override(course_factory, college_factory):
    college = college_factory()
    curriculum = Curriculum.objects.create(short_name="SCI", college=college)
    course = course_factory(college=college, credit_hours=3)
    cc = CurriculumCourse.objects.create(
        curriculum=curriculum,
        course=course,
        credit_hours=4,
    )
    assert cc.effective_credit_hours == 4


@pytest.mark.django_db
def test_effective_credit_hours_fallback(course_factory, college_factory):
    college = college_factory()
    curriculum = Curriculum.objects.create(short_name="SCI", college=college)
    course = course_factory(college=college, credit_hours=3)
    cc = CurriculumCourse.objects.create(
        curriculum=curriculum,
        course=course,
        credit_hours=None,
    )
    assert cc.effective_credit_hours == 3
