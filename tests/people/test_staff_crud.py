import pytest
from django.db import connection
from app.shared.status.mixins import StatusHistory
from app.people.models.staffs import Staff


@pytest.mark.django_db
def test_staff_crud(staff_factory, department):
    """CRUD operations for Staff."""
    tables = connection.introspection.table_names()
    if StatusHistory._meta.db_table not in tables:
        pytest.skip("StatusHistory table not present in SQLite tests")
    staff = staff_factory("crudstaff", department)
    assert Staff.objects.filter(pk=staff.pk).exists()

    fetched = Staff.objects.get(pk=staff.pk)
    assert fetched == staff

    fetched.position = "Updated"
    fetched.save()
    updated = Staff.objects.get(pk=staff.pk)
    assert updated.position == "Updated"

    updated.delete()
    assert not Staff.objects.filter(pk=staff.pk).exists()
