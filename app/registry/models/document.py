"""Document module."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, cast, Self


from app.shared.mixins import SimpleTableMixin
from django.db import models
from simple_history.models import HistoricalRecords

from app.shared.status.mixins import StatusableMixin, StatusHistory


def set_document_path(instance, filename: str) -> str:
    """Set the directory where to save the filename.

    MEDIA_ROOT/<instance_name>/<instance.person>.
    """
    instance_name = instance.__class__.__name__.lower()
    return str(Path(instance_name) / str(instance.person) / filename)


class DocumentType(SimpleTableMixin):
    PHOTO = "photo", "Photo"
    APPLET = "applet", "Application Letter"
    RECLS = "recls", "Recommandation Last School"
    RECCOM = "reccom", "Recommandation Community"
    RECREL = "recrel", "Recommandation Relgious Leaders"
    MEDCERT = "medcert", "Medical Certificat"
    REPCARD = "repcard", "Report Card"
    WAEC = "waec", "Waec"
    BILL = "bill", "Bill"
    TRANSCRIPT = "transcript", "Transcript"
    PUBLIC = "public", "Public_signature"
    OTHER = "other", "Other Document"
    DEFAULT_VALUES = [
        "public",
        "transcript",
        "bill",
        "waec",
        "repcard",
        "medcert",
        "recrel" "recls",
        "reccom",
        "applet",
        "photo",
    ]

    @classmethod
    def get_default(cls) -> Self:
        """Returns the default FeeType."""
        deft, _ = cls.objects.get_or_create(code="other", label="Other Document")
        return deft


class DocumentStatus(SimpleTableMixin):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    ADJUSTMENTS_REQUIRED = "adjustments_required", "Adjustments Required"
    REJECTED = "rejected", "Rejected"
    DEFAULT_VALUES = [
        "rejected",
        "adjustments_required",
        "approved",
        "pending",
    ]

    @classmethod
    def get_default(cls) -> Self:
        """Returns the default FeeType."""
        deft, _ = cls.objects.get_or_create(code=cls.PENDING[0], label=cls.PENDING[1])
        return deft


class AbstractDocument(StatusableMixin, models.Model):
    """Abstract / factorize some of the documents common methods.

    I'm not abstracting all because historicalRecords need concreet class.
    """

    class Meta:
        abstract = True
        """Model metadata."""

    # ~~~~~~~~ Mandatory ~~~~~~~~
    # ~~~~ Auto-filled ~~~~
    data_file = models.FileField(upload_to=set_document_path)
    status = models.ForeignKey(
        "registry.DocumentStatus",
        on_delete=models.PROTECT,
        related_name="%(class)s",
        related_query_name="%(class)s",
        verbose_name="Validation Status",
    )

    document_type = models.ForeignKey(
        "registry.DocumentType",
        on_delete=models.PROTECT,
        related_name="%(class)s",
        related_query_name="%(class)s",
        verbose_name="Document Types",
    )

    def current_status(self) -> Optional[StatusHistory]:
        """Return the most recent status entry or None if empty."""

        return cast(Optional[StatusHistory], self.status_history.first())

    def clean(self) -> None:
        """Validating the change of DocumentStatus."""
        super().clean()

    def _ensure_document_status(self):
        """Ensure we have a document Status."""
        if not self.status_id:
            self.status = DocumentStatus.get_default()

    def _ensure_document_type(self):
        """Ensure we have a document Type."""
        if not self.document_type_id:
            self.document_type = DocumentType.get_default()

    # need to set a default for status when saving.
    def save(self, *args, **kwargs):
        """Set default before save."""
        self._ensure_document_status()
        self._ensure_document_type()
        return super().save(*args, **kwargs)

    # >? Is it possible to have class method in an abstract class ?
    # I think not because the class is neve insta..


class DocumentStudent(AbstractDocument):
    """Store the students documents."""

    # ~~~~~~~~ Mandatory ~~~~~~~~
    person = models.ForeignKey(
        "people.Student",
        on_delete=models.CASCADE,
        related_name="student_docs",
    )
    # ~~~~ Auto-filled ~~~~
    history = HistoricalRecords()


class DocumentDonor(AbstractDocument):
    """Store the donors documents."""

    # ~~~~~~~~ Mandatory ~~~~~~~~
    person = models.ForeignKey(
        "people.Donor",
        on_delete=models.CASCADE,
        related_name="donor_docs",
    )
    # ~~~~ Auto-filled ~~~~
    history = HistoricalRecords()


class DocumentStaff(AbstractDocument):
    """Store the staffs documents."""

    # ~~~~~~~~ Mandatory ~~~~~~~~
    person = models.ForeignKey(
        "people.Staff",
        on_delete=models.CASCADE,
        related_name="staff_docs",
    )
    # ~~~~ Auto-filled ~~~~
    history = HistoricalRecords()
