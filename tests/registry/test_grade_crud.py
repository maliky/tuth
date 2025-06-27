import pytest
from app.registry.models.grade import Grade
from app.academics.models.program import Program
from app.timetable.models.section import Section


@pytest.mark.django_db
def test_grade_crud(student, course_factory, curriculum_empty, semester):
    """CRUD operations for Grade."""
    course = course_factory("201")
    program = Program.objects.create(curriculum=curriculum_empty, course=course)
    section = Section.objects.create(
        program=program,
        semester=semester,
        number=1,
        start_date=semester.start_date,
        end_date=semester.end_date,
    )
    grade = Grade.objects.create(
        student=student,
        section=section,
        letter_grade="A",
        numeric_grade=95,
    )
    assert Grade.objects.filter(pk=grade.pk).exists()

    fetched = Grade.objects.get(pk=grade.pk)
    assert fetched == grade

    fetched.letter_grade = "B"
    fetched.save()
    updated = Grade.objects.get(pk=grade.pk)
    assert updated.letter_grade == "B"

    updated.delete()
    assert not Grade.objects.filter(pk=grade.pk).exists()
