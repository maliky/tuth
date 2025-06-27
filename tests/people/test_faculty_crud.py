import pytest
from django.db import connection
from app.shared.status.mixins import StatusHistory
from app.people.models.staffs import Faculty


@pytest.mark.django_db
def test_faculty_crud(faculty: Faculty):
    """CRUD operations for Faculty."""
    tables = connection.introspection.table_names()
    if StatusHistory._meta.db_table not in tables:
        pytest.skip("StatusHistory table not present in SQLite tests")
    assert Faculty.objects.filter(pk=faculty.pk).exists()

    fetched = Faculty.objects.get(pk=faculty.pk)
    assert fetched == faculty

    fetched.academic_rank = "Prof"
    fetched.save()
    updated = Faculty.objects.get(pk=faculty.pk)
    assert updated.academic_rank == "Prof"

    updated.delete()
    assert not Faculty.objects.filter(pk=faculty.pk).exists()
