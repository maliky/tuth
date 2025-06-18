"""Constants for the :mod:`finance` app.

This module defines enumerations representing various aspects of the
financial domain such as payment methods, fee types and student
clearance statuses.  It also exposes the ``TUITION_RATE_PER_CREDIT``
value used when computing tuition."""

from decimal import Decimal
from django.db import models


class StatusClearance(models.TextChoices):
    PENDING = "pending", "Pending"
    CLEARED = "cleared", "Cleared"
    BLOCKED = "blocked", "Blocked"


class PaymentMethod(models.TextChoices):
    CASH = "cash", "Cash"
    CRYPTO = "crypto", "Crypto (ADA)"
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
