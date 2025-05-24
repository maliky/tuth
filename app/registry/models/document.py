from __future__ import (
    annotations,
)

from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from app.people.models import StudentProfile
from app.shared.constants import DOCUMENT_TYPES
from app.shared.utils import make_choices, validate_model_status


class Document(models.Model):
    student_profil = models.ForeignKey(StudentProfile, on_delete=models.CASCADE)
    file = models.FileField(upload_to="documents/")
    document_type = models.CharField(max_length=50, choices=make_choices(DOCUMENT_TYPES))
    status_history = GenericRelation(
        "shared.StatusHistory", related_query_name="document"
    )

    def current_status(self):
        """Return the most recent status entry or ``None`` if empty."""
        return self.status_history.first()

    def clean(self):
        super().clean()
        validate_model_status(self)
