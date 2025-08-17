"""Choice module for finance app."""

from app.shared.mixins import StatusMixin
from typing import Self


class ClearanceStatus(StatusMixin):
    """Clearance Statuses."""

    @classmethod
    def cleared(cls):
        """Return the cleared status."""
        status, _ = cls.objects.get_or_create(code="cleared")
        return status

    @classmethod
    def get_default(cls) -> Self:
        """Returns the default ClearanceStatus."""
        deft, _ = cls.objects.get_or_create(code="pending")
        return deft

    # PENDING = "pending", "Pending"
    # CLEARED = "cleared", "Cleared"
    # BLOCKED = "blocked", "Blocked"


class PaymentMethod(StatusMixin):
    """Payment method statuses."""

    @classmethod
    def get_default(cls) -> Self:
        """Returns the default PaymentMethod."""
        deft, _ = cls.objects.get_or_create(code="cash")
        return deft

    # CASH = "cash", "Cash"
    # CRYPTO = "crypto", "Crypto (ADA)"
    # MOBILE_MONEY = "mobile_money", "Mobile Money"
    # WIRE = "wire", "Wire"


class FeeType(StatusMixin):
    """Enumeration of fee types."""

    @classmethod
    def get_default(cls) -> Self:
        """Returns the default FeeType."""
        deft, _ = cls.objects.get_or_create(code="other")
        return deft

    # CREDIT_HOUR_FEE = "CREDIT_HOUR_FEE", "Credit Hour Fee"
    # LAB = "lab", "Lab"
    # OTHER = "other", "Other"
    # RESEARCH = "research", "Research"
    # TUITION = "tuition", "Tuition"
