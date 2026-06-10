"""Compatibility façade for finance admin registrations."""

from __future__ import annotations

from app.finance.admin.fee_stack_admin import (
    CrsFeeStackAdmin,
    CrsFeeStackIL,
    FeeStackAdmin,
    FeeStackLineAdmin,
    FeeStackLineIL,
)
from app.finance.admin.invoice_admin import (
    AmountDueFlt,
    CrsInvoiceAdmin,
    StaffChoiceField,
    StdSemInvoiceAdmin,
)
from app.finance.admin.payment_admin import LookupAdmin, PaymentAdmin
from app.finance.admin.scholarship_admin import ScholarshipAdmin

__all__ = [
    "AmountDueFlt",
    "CrsFeeStackAdmin",
    "CrsFeeStackIL",
    "CrsInvoiceAdmin",
    "FeeStackAdmin",
    "FeeStackLineAdmin",
    "FeeStackLineIL",
    "LookupAdmin",
    "PaymentAdmin",
    "ScholarshipAdmin",
    "StaffChoiceField",
    "StdSemInvoiceAdmin",
]
