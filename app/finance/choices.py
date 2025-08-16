"""Choice module for finance app."""

from app.shared.mixins import StatusMixin


class ClearanceStatus(StatusMixin):
    """Clearance Statuses."""

    # PENDING = "pending", "Pending"
    # CLEARED = "cleared", "Cleared"
    # BLOCKED = "blocked", "Blocked"


class PaymentMethod(StatusMixin):
    """Payment method statuses."""

    # CASH = "cash", "Cash"
    # CRYPTO = "crypto", "Crypto (ADA)"
    # MOBILE_MONEY = "mobile_money", "Mobile Money"
    # WIRE = "wire", "Wire"


class FeeType(StatusMixin):
    """Enumeration of fee types."""

    # CREDIT_HOUR_FEE = "CREDIT_HOUR_FEE", "Credit Hour Fee"
    # LAB = "lab", "Lab"
    # OTHER = "other", "Other"
    # RESEARCH = "research", "Research"
    # TUITION = "tuition", "Tuition"
