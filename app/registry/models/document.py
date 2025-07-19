"""Document module."""

from __future__ import annotations

from typing import Optional, cast

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from simple_history.models import HistoricalRecords

from app.registry.choices import DocumentType, StatusDocument
from app.shared.status.mixins import StatusableMixin, StatusHistory


class Document(StatusableMixin, models.Model):
    """File uploaded to support a user profile.

    The profile generic relation allows attaching documents to different
    profile models (students, staff, etc.).

    Example:
        >>> from app.registry.models.documnets import Document
        >>> doc = Document.objects.create(
        ...     profile=student_profile,
        ...     file="id.pdf",
        ...     document_type=DocumentType.ID_CARD,
        ... )
        >>> doc.set_pending(author=None)
    Side Effects:
        Status changes are tracked via status_history.
    """

    # ! the folowing 2 are not too clear. needs clarifications

    # ~~~~~~~~ Mandatory ~~~~~~~~
    profile_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    profile_id = models.PositiveIntegerField()
    profile = GenericForeignKey("profile_type", "profile_id")
    data_file = models.FileField(upload_to="documents/")
    document_type = models.CharField(max_length=50, choices=DocumentType.choices)
    # ~~~~ Auto-filled ~~~~
    status = models.CharField(
        max_length=30,
        choices=StatusDocument.choices,
        default=StatusDocument.PENDING,
    )
    history = HistoricalRecords()

    def current_status(self) -> Optional[StatusHistory]:
        """Return the most recent status entry or None if empty."""

        return cast(Optional[StatusHistory], self.status_history.first())

    def clean(self) -> None:
        """Validating the change of DocumentStatus."""
        super().clean()
        self.validate_status(StatusDocument)

    class Meta:
        """Model metadata."""

        # Index both components of the generic relation to speed up lookups
        indexes = [
            models.Index(fields=["profile_type", "profile_id"]),
        ]
