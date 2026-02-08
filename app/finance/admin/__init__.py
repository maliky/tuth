"""Initialization for the admin package."""

from app.finance.admin.core import (
    CourseInvoiceAdmin,
    LookupAdmin,
    PaymentAdmin,
    ScholarshipAdmin,
    StudentSemesterInvoiceAdmin,
)


__all__ = [
    "CourseInvoiceAdmin",
    "LookupAdmin",
    "PaymentAdmin",
    "ScholarshipAdmin",
    "StudentSemesterInvoiceAdmin",
]
