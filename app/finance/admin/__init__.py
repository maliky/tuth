"""Initialization for the admin package."""

from app.finance.admin.core import (
    CrsInvoiceAdmin,
    LookupAdmin,
    PaymentAdmin,
    ScholarshipAdmin,
    StdSemInvoiceAdmin,
)


__all__ = [
    "CrsInvoiceAdmin",
    "LookupAdmin",
    "PaymentAdmin",
    "ScholarshipAdmin",
    "StdSemInvoiceAdmin",
]
