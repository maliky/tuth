import pytest
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from app.shared.status.mixins import StatusHistory
from app.registry.models.document import Document
from app.people.models.donor import Donor


@pytest.mark.django_db
def test_document_crud(donor):
    """CRUD operations for Document."""
    tables = connection.introspection.table_names()
    if StatusHistory._meta.db_table not in tables:
        pytest.skip("StatusHistory table not present in SQLite tests")
    ct = ContentType.objects.get_for_model(Donor)
    doc = Document.objects.create(
        profile_type=ct,
        profile_id=donor.pk,
        data_file="tmp.txt",
        document_type="id_card",
    )
    assert Document.objects.filter(pk=doc.pk).exists()

    fetched = Document.objects.get(pk=doc.pk)
    assert fetched == doc

    fetched.document_type = "passport"
    fetched.save()
    updated = Document.objects.get(pk=doc.pk)
    assert updated.document_type == "passport"

    updated.delete()
    assert not Document.objects.filter(pk=doc.pk).exists()
