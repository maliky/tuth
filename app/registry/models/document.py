from __future__ import (
    annotations,
)

from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models
from app.shared.utils import validate_model_status


class Document(models.Model):
    profile_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    profile_id = models.PositiveIntegerField()
    profile = GenericForeignKey("profile_type", "profile_id")
    file = models.FileField(upload_to="documents/")
    document_type = models.CharField(max_length=50)
    status_history = GenericRelation(
        "shared.StatusHistory", related_query_name="document"
    )

    def current_status(self):
        """Return the most recent status entry or ``None`` if empty."""
        return self.status_history.first()

    def clean(self):
        super().clean()
        validate_model_status(self)
