"""Document module."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, cast


from django.db import models
from simple_history.models import HistoricalRecords

from app.registry.choices import DocumentType, StatusDocument
from app.shared.status.mixins import StatusableMixin, StatusHistory


def set_document_path(instance, filename):
    """Set the directory where to save the filename.

    MEDIA_ROOT/<instance_name>/<instance.person>
    """
    instance_name = instance.__class__.__name__.lower()
    return str(Path(instance_name) / instance.person / filename)


class AbstractDocument(StatusableMixin, models.Model):
    """Abstract / factorize some of the documents common methods.

    I'm not abstracting all because historicalRecords need concreet class.
    """

    # ~~~~~~~~ Mandatory ~~~~~~~~
    # ~~~~ Auto-filled ~~~~
    data_file = models.FileField(upload_to=set_document_path)
    status = models.CharField(
        max_length=30,
        choices=StatusDocument.choices,
        default=StatusDocument.PENDING,
    )

    def current_status(self) -> Optional[StatusHistory]:
        """Return the most recent status entry or None if empty."""

        return cast(Optional[StatusHistory], self.status_history.first())

    def clean(self) -> None:
        """Validating the change of DocumentStatus."""
        super().clean()

    class Meta:
        abstract = True
        """Model metadata."""


class DocumentStudent(AbstractDocument):
    """Store the students documents."""

    # ~~~~~~~~ Mandatory ~~~~~~~~
    person = models.ForeignKey(
        "people.Student",
        on_delete=models.CASCADE,
        related_name="documents",
    )

    # may update this to document type for student, donor and staff
    document_type = models.CharField(max_length=50, choices=DocumentType.choices)
    # ~~~~ Auto-filled ~~~~
    history = HistoricalRecords()


class DocumentDonor(AbstractDocument):
    """Store the donors documents."""

    # ~~~~~~~~ Mandatory ~~~~~~~~
    person = models.ForeignKey(
        "people.Donor",
        on_delete=models.CASCADE,
        related_name="documents",
    )
    document_type = models.CharField(max_length=50, choices=DocumentType.choices)
    # ~~~~ Auto-filled ~~~~
    history = HistoricalRecords()


class DocumentStaff(AbstractDocument):
    """Store the staffs documents."""

    # ~~~~~~~~ Mandatory ~~~~~~~~
    person = models.ForeignKey(
        "people.Staff",
        on_delete=models.CASCADE,
        related_name="documents",
    )
    document_type = models.CharField(max_length=50, choices=DocumentType.choices)
    # ~~~~ Auto-filled ~~~~
    history = HistoricalRecords()
