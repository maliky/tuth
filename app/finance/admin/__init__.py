"""Initialization for the admin package."""

from app.finance.admin.core import (
    CrsInvoiceAdmin,
    LookupAdmin,
    PaymentAdmin,
    ScholarshipAdmin,
    StdSemInvoiceAdmin,
    TuitionRateAdmin,
)


__all__ = [
    "CrsInvoiceAdmin",
    "LookupAdmin",
    "PaymentAdmin",
    "ScholarshipAdmin",
    "StdSemInvoiceAdmin",
    "TuitionRateAdmin",
]
