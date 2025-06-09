"""Registry module."""

from django.db import models


class DocumentType(models.TextChoices):
    WAEC = "waec", "Waec"
    BILL = "bill", "Bill"
    TRANSCRIPT = "transcript", "Transcript"
    PUBLIC = "public", "Public_signature"


class StatusRegistration(models.TextChoices):
    PENDING = "pending payment", "Pending Payment"
    FINANCIALLY_CLEARED = "financially_cleared", "Financially_Cleared"
    COMPLETED = "completed", "Completed"
    APPROVED = "approved", "Approved"


class StatusDocument(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    ADJUSTMENTS_REQUIRED = "adjustments_required", "Adjustments Required"
    REJECTED = "rejected", "Rejected"
