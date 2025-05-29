from decimal import Decimal
from django.db import models


class PaymentMethod(models.TextChoices):
    CASH = "cash", "Cash"
    MOBILE_MONEY = "mobile_money", "Mobile Money"
    CRYPTO = "crytpo", "Crypto (ADA)"
    WIRE = "wire", "Wire"    


class FeeTypeLabels(models.TextChoices):
    """Enumeration of fee types."""

    TUITION = "tuition", "Tuition"
    LAB = "lab", "Lab"
    RESEARCH = "research", "Research"
    OTHER = "other", "Other"


class StatusReservation(models.TextChoices):
    REQUESTED = "requested", "Requested"
    VALIDATED = "validated", "Validated"
    CANCELLED = "cancelled", "Cancelled"
    PAID = "paid", "Paid"


TUITION_RATE_PER_CREDIT = Decimal("5.00")
