"""Initialization for the admin package."""
from app.finance.admin.core import (
    InvoiceAdmin,
    LookupAdmin,
    PaymentAdmin,
    ScholarshipAdmin,
)


__all__ = ["InvoiceAdmin", "PaymentAdmin", "ScholarshipAdmin", "LookupAdmin"]
