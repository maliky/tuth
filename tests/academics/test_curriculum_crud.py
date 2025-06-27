import pytest
from app.shared.status.mixins import StatusHistory
from django.db import connection

from app.academics.models.curriculum import Curriculum


@pytest.mark.django_db
def test_curriculum_crud(college_factory):
    # create
    college = college_factory()
    curriculum = Curriculum.objects.create(
        short_name="BSCM",
        long_name="Computer Management",
        college=college,
    )
    assert Curriculum.objects.filter(pk=curriculum.pk).exists()

    # read
    fetched = Curriculum.objects.get(pk=curriculum.pk)
    assert fetched == curriculum

    # update
    fetched.long_name = "Computer Management Updated"
    fetched.save()
    updated = Curriculum.objects.get(pk=curriculum.pk)
    assert updated.long_name == "Computer Management Updated"

    # delete
    tables = connection.introspection.table_names()
    if StatusHistory._meta.db_table not in tables:
        from django.db import connection as conn
        with conn.schema_editor() as schema:
            schema.create_model(StatusHistory)
    updated.delete()
    assert not Curriculum.objects.filter(pk=curriculum.pk).exists()

