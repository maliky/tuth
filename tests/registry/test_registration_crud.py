import pytest
from django.db import connection
from app.shared.status.mixins import StatusHistory
from app.registry.models.registration import Registration
from app.academics.models.program import Program
from app.timetable.models.section import Section


@pytest.mark.django_db
def test_registration_crud(student, course_factory, curriculum_empty, semester):
    """CRUD operations for Registration."""
    tables = connection.introspection.table_names()
    if StatusHistory._meta.db_table not in tables:
        pytest.skip("StatusHistory table not present in SQLite tests")
    course = course_factory("301")
    program = Program.objects.create(curriculum=curriculum_empty, course=course)
    section = Section.objects.create(
        program=program,
        semester=semester,
        number=1,
        start_date=semester.start_date,
        end_date=semester.end_date,
    )
    reg = Registration.objects.create(student=student, section=section)
    assert Registration.objects.filter(pk=reg.pk).exists()

    fetched = Registration.objects.get(pk=reg.pk)
    assert fetched == reg

    fetched.status = "approved"
    fetched.save()
    updated = Registration.objects.get(pk=reg.pk)
    assert updated.status == "approved"

    updated.delete()
    assert not Registration.objects.filter(pk=reg.pk).exists()
