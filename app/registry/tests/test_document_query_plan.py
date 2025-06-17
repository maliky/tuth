"""Ensure document lookups benefit from the compound profile index."""

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile

from app.registry.models.document import Document
from app.shared.constants.registry import DocumentType
from app.people.models.others import Student


@pytest.mark.django_db
def test_document_query_uses_profile_index(student_profile):
    # > Need to harmonize variable names in the tests.  Use ct is good for content.
    ct = ContentType.objects.get_for_model(Student)
    for _ in range(3):
        Document.objects.create(
            profile_type=ct,
            profile_id=student_profile.pk,
            file=SimpleUploadedFile("doc.txt", b"content"),
            document_type=DocumentType.WAEC,
        )

    query = Document.objects.filter(profile_type=ct, profile_id=student_profile.pk)
    plan = query.explain().upper()
    assert "USING INDEX" in plan or "SEARCH" in plan
