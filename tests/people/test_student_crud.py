import pytest
from django.db import connection
from app.shared.status.mixins import StatusHistory
from app.people.models.student import Student


@pytest.mark.django_db
def test_student_crud(student: Student):
    """CRUD operations for Student."""
    tables = connection.introspection.table_names()
    if StatusHistory._meta.db_table not in tables:
        pytest.skip("StatusHistory table not present in SQLite tests")
    assert Student.objects.filter(pk=student.pk).exists()

    fetched = Student.objects.get(pk=student.pk)
    assert fetched == student

    fetched.phone_number = "000"
    fetched.save()
    updated = Student.objects.get(pk=student.pk)
    assert updated.phone_number == "000"

    updated.delete()
    assert not Student.objects.filter(pk=student.pk).exists()
