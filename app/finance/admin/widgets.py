"""Import/export widgets for finance admin."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from import_export import widgets

from app.academics.admin.widgets import CurriCourseWgt
from app.finance.models.invoice import CourseInvoice, StdSemesterInvoice
from app.finance.models.status_types_methods import (
    FeeType,
    InvoiceStatus,
    Payer,
    PaymentMethod,
    PaymentStatus,
)
from app.people.admin.widgets import StaffProfileWgt, StdUserWgt
from app.shared.utils import get_in_row, parse_str
from app.timetable.admin.core_widgets import SemesterWgt


class SimpleCodeWgt(widgets.ForeignKeyWidget):
    """Resolve simple lookup tables by their code."""

    def clean(self, value, row=None, *args, **kwargs):
        """Return or create the lookup row by code."""
        code = parse_str(value)
        if not code:
            return None
        obj, _ = self.model.objects.get_or_create(code=code)
        return obj

    def render(self, value, obj=None):
        """Export the code for the lookup row."""
        return getattr(value, "code", "") if value else ""


class FeeTypeWgt(SimpleCodeWgt):
    """Resolve FeeType entries by code."""

    def __init__(self):
        super().__init__(FeeType, field="code")


class PaymentMethodWgt(SimpleCodeWgt):
    """Resolve PaymentMethod entries by code."""

    def __init__(self):
        super().__init__(PaymentMethod, field="code")


class PaymentStatusWgt(SimpleCodeWgt):
    """Resolve PaymentStatus entries by code."""

    def __init__(self):
        super().__init__(PaymentStatus, field="code")


class InvoiceStatusWgt(SimpleCodeWgt):
    """Resolve InvoiceStatus entries by code."""

    def __init__(self):
        super().__init__(InvoiceStatus, field="code")


class PayerWgt(SimpleCodeWgt):
    """Resolve Payer entries by code."""

    def __init__(self):
        super().__init__(Payer, field="code")


class InvoiceWgt(widgets.ForeignKeyWidget):
    """Resolve course invoices using student, curriculum course, and semester."""

    def __init__(self):
        super().__init__(CourseInvoice)
        self.student_w = StdUserWgt()
        self.curriculum_course_w = CurriCourseWgt()
        self.semester_w = SemesterWgt()

    def _parse_amount(self, value: str) -> Decimal:
        token = parse_str(value)
        if not token:
            return Decimal("0.00")
        try:
            return Decimal(token)
        except (TypeError, ValueError):
            return Decimal("0.00")

    def clean(self, value, row=None, *args, **kwargs) -> Optional[CourseInvoice]:
        """Return or create an invoice using human-readable row columns."""
        student_value = get_in_row("student_id", row)
        curriculum_value = get_in_row("curriculum", row)
        semester_value = get_in_row("semester_no", row) or get_in_row("semester", row)

        student = self.student_w.clean(student_value, row=row)
        curriculum_course = self.curriculum_course_w.clean(curriculum_value, row=row)
        semester = self.semester_w.clean(semester_value, row=row)

        if not (student and curriculum_course and semester):
            return None

        invoice = CourseInvoice.objects.filter(
            student=student,
            curriculum_course=curriculum_course,
            semester=semester,
        ).first()
        if invoice:
            return invoice

        initial_due = self._parse_amount(get_in_row("initial_amount_due", row))
        balance = self._parse_amount(get_in_row("balance", row)) or initial_due

        return CourseInvoice.objects.create(
            student=student,
            curriculum_course=curriculum_course,
            semester=semester,
            initial_amount_due=initial_due,
            balance=balance,
        )


class StdSemesterInvoiceWgt(widgets.ForeignKeyWidget):
    """Resolve parent invoices using student and semester columns."""

    def __init__(self):
        super().__init__(StdSemesterInvoice)
        self.student_w = StdUserWgt()
        self.semester_w = SemesterWgt()

    def clean(self, value, row=None, *args, **kwargs) -> Optional[StdSemesterInvoice]:
        """Return or create a parent invoice from student+semester row columns."""
        student_value = get_in_row("student_id", row)
        semester_value = get_in_row("semester_no", row) or get_in_row("semester", row)
        student = self.student_w.clean(student_value, row=row)
        semester = self.semester_w.clean(semester_value, row=row)
        if not (student and semester):
            return None
        parent_invoice, _ = StdSemesterInvoice.objects.get_or_create(
            student=student,
            semester=semester,
        )
        return parent_invoice


class StaffWgt(StaffProfileWgt):
    """Alias for staff widget with a clearer name in finance resources."""
