"""status and types for regsitry app."""

from typing import cast
from app.shared.mixins import SimpleTableMixin


class DocumentType(SimpleTableMixin):

    DEFAULT_VALUES = [
        ("photo", "Photo"),
        ("applet", "Application Letter"),
        ("recls", "Recommandation Last School"),
        ("reccom", "Recommandation Community"),
        ("recrel", "Recommandation Relgious Leaders"),
        ("medcert", "Medical Certificat"),
        ("repcard", "Report Card"),
        ("waec", "Waec"),
        ("bill", "Bill"),
        ("transcript", "Transcript"),
        ("public", "Public_signature"),
        ("other", "Other Document"),
    ]

    @classmethod
    def get_default(cls) -> Self:
        """Returns the default FeeType."""
        deft, _ = cls.objects.get_or_create(
            code="other", defaults={"label": "Other Document"}
        )
        return cast(Self, deft)


class DocumentStatus(SimpleTableMixin):
    DEFAULT_VALUES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("adjustments_required", "Adjustments Required"),
        ("rejected", "Rejected"),
    ]

    class Meta:
        verbose_name_plural = "Document Status"

    @classmethod
    def get_default(cls) -> Self:
        """Returns the default FeeType."""
        deft, _ = cls.objects.get_or_create(code="pending", defaults={"label": "Pending"})
        return cast(Self, deft)


class TranscriptRequestStatus(SimpleTableMixin):
    """Lookup table storing allowed states for transcript requests."""

    DEFAULT_VALUES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("on_hold", "On hold"),
    ]

    class Meta:
        verbose_name_plural = "Transcript Request Status"

    @classmethod
    def get_default(cls):
        """Return the default status."""
        default, _ = cls.objects.get_or_create(
            code="pending", defaults={"label": "Pending"}
        )
        return default


class RegistrationStatus(SimpleTableMixin):
    DEFAULT_VALUES = [
        ("pending", "Pending Payment"),
        ("partial", "Partialy Approved"),
        ("cleared", "Financially Cleared"),
    ]

    class Meta:
        verbose_name_plural = "Registration Status"

    @classmethod
    def get_default(cls) -> Self:
        """Returns the default FeeType."""
        deft, _ = cls.objects.get_or_create(
            code="pending", defaults={"label": "Pending Payment"}
        )
        return cast(Self, deft)
