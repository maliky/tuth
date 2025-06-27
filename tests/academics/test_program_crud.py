import pytest
from app.academics.models.curriculum import Curriculum
from app.academics.models.program import Program


@pytest.mark.django_db
def test_program_crud(course_factory, college_factory):
    # create related objects
    college = college_factory()
    curriculum = Curriculum.objects.create(short_name="TPRG", college=college)
    course = course_factory("201", "Advanced")
    program = Program.objects.create(curriculum=curriculum, course=course)
    assert Program.objects.filter(pk=program.pk).exists()

    # read
    fetched = Program.objects.get(pk=program.pk)
    assert fetched == program

    # update
    fetched.is_required = False
    fetched.save()
    updated = Program.objects.get(pk=program.pk)
    assert updated.is_required is False

    # delete
    updated.delete()
    assert not Program.objects.filter(pk=program.pk).exists()

