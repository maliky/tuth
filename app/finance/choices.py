"""Choice module for finance app."""

from app.shared.mixins import SimpleTableMixin
from typing import Self


class ClearanceStatus(SimpleTableMixin):
    """Clearance Statuses."""

    PENDING = "pending", "Pending"
    CLEARED = "cleared", "Cleared"
    BLOCKED = "blocked", "Blocked"

    TABLE_DEFAULT_VALUES = ["pending", "cleared", "blocked"]

    @classmethod
    def get_default(cls) -> Self:
        """Returns the default ClearanceStatus."""

        deft, _ = cls.objects.get_or_create(code=cls.PENDING[0], label=cls.PENDING[1])
        return deft


class PaymentMethod(SimpleTableMixin):
    """Payment method statuses."""

    CASH = "cash", "Cash"
    CRYPTO = "crypto", "Crypto (ADA)"
    MOBILE_MONEY = "mobile_money", "Mobile Money"
    WIRE = "wire", "Wire"
    TABLE_DEFAULT_VALUES = ["wire", "mobile Money", "crypto_ada", "cash"]

    @classmethod
    def get_default(cls) -> Self:
        """Returns the default PaymentMethod."""
        deft, _ = cls.objects.get_or_create(code=cls.CASH[0], label=cls.CASH[1])
        return deft


class FeeType(SimpleTableMixin):
    """Enumeration of fee types."""

    CREDIT_HOUR_FEE = "CREDIT_HOUR_FEE", "Credit Hour Fee"
    LAB = "lab", "Lab"
    OTHER = "other", "Other"
    RESEARCH = "research", "Research"
    TUITION = "tuition", "Tuition"
    TABLE_DEFAULT_VALUES = [
        "tuition",
        "research",
        "other",
        "lab",
        "credit_hour_fee",
    ]

    @classmethod
    def get_default(cls) -> Self:
        """Returns the default FeeType."""
        deft, _ = cls.objects.get_or_create(code=cls.OTHER[0], label=cls.OTHER[1])
        return deft
