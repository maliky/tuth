from django.db import models

DOCUMENT_TYPES: list[str] = [
    "waec",
    "bill",
    "transcript",
]


class StatusRegistration(models.TextChoices):
    PENDING = "pending payment", "Pending Payment"
    FINANCIALY_CLEARED = "financialy_cleared", "Financialy_Cleared"
    COMPLETED = "completed", "Completed"
    APPROVED = "approved", "Approved"
