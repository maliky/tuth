from decimal import Decimal
from django.db import models


class StatusClearance(models.TextChoices):
    PENDING = "pending", "Pending"
    CLEARED = "cleared", "Cleared"
    BLOCKED = "blocked", "Blocked"


class PaymentMethod(models.TextChoices):
    CASH = "cash", "Cash"
    CRYPTO = "crytpo", "Crypto (ADA)"
    MOBILE_MONEY = "mobile_money", "Mobile Money"
    WIRE = "wire", "Wire"


class FeeType(models.TextChoices):
    """Enumeration of fee types."""

    CREDIT_HOUR_FEE = "CREDIT_HOUR_FEE", "Credit Hour Fee"
    LAB = "lab", "Lab"
    OTHER = "other", "Other"
    RESEARCH = "research", "Research"
    TUITION = "tuition", "Tuition"


TUITION_RATE_PER_CREDIT = Decimal("5.00")
