"""Payment module."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import models
from simple_history.models import HistoricalRecords

from app.academics.models.curriculum_course import CurriculumCourse
from app.finance.models.status_types_methods import InvoiceStatus
from app.people.models.student import Student
from app.registry.models.registration import Registration
from app.registry.models.status_types import RegistrationStatus
from app.shared.mixins import StatusableMixin
from app.timetable.models.semester import Semester


class Invoice(StatusableMixin, models.Model):
    """Invoice for a curriculum_course.

    Attributes:
        curriculum_course: Course in a curriculum being paid for.
        student: Student responsible for the invoice.
        semester: Semester associated with the charge.
        initial_amount_due: Original total for the invoice.
        recorded_by: Staff member who logged the payment.
        scholarship: Optional scholarship applied.

    A student can pay several times for the same curriculum_course.
    For eg if they fail. then they need to retake it.
    It is ok as the semester will differ.

    The scholarship can modify the invoice as some fee will be taken car off.

    Example:
        >>> from decimal import Decimal
        >>> from app.academics.models.curriculum_course import CurriculumCourse
        >>> from app.people.models.student import Student
        >>> from app.timetable.models.semester import Semester
        >>> Invoice.objects.create(
        ...     curriculum_course=CurriculumCourse.get_default(),
        ...     student=Student.get_default(),
        ...     semester=Semester.get_current_semester(),
        ...     initial_amount_due=Decimal("10.00"),
        ...     balance=Decimal("10.00"),
        ... )
    """

    # ~~~~~~~~ Mandatory ~~~~~~~~
    curriculum_course = models.ForeignKey(
        "academics.CurriculumCourse", on_delete=models.CASCADE
    )
    student = models.ForeignKey("people.Student", on_delete=models.PROTECT)
    semester = models.ForeignKey("timetable.Semester", on_delete=models.PROTECT)
    initial_amount_due = models.DecimalField(max_digits=8, decimal_places=2)
    # ~~~~ Auto-filled ~~~~
    status = models.ForeignKey(
        "finance.InvoiceStatus",
        on_delete=models.PROTECT,
        related_name="invoices",
        default="initial",
    )

    balance = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    history = HistoricalRecords()
    created_at = models.DateTimeField(auto_now_add=True)

    # ~~~~~~~~ Optional ~~~~~~~~
    recorded_by = models.ForeignKey(
        "people.Staff",
        null=True,
        on_delete=models.SET_NULL,
    )
    scholarship = models.ForeignKey(
        "finance.scholarship", on_delete=models.PROTECT, null=True
    )

    def get_balance(self) -> Decimal:
        """Return the balance."""
        if self.balance is None:
            self.balance = self.initial_amount_due
        return self.balance

    def __str__(self) -> str:  # pragma: no cover
        """Return a concise representation of the payment."""
        return f"{self.curriculum_course} - {self.balance}"

    def _update_status(self) -> None:
        """Update the invoice status based on balance."""
        balance = self.get_balance()
        if balance == self.initial_amount_due:
            self.status = InvoiceStatus.initial()
        elif balance == 0:
            self.status = InvoiceStatus.cleared()
        elif balance <= self.clearance_balance():
            self.status = InvoiceStatus.settled()
        else:
            # self.clearance_balance() < self.balance < self.initial_amount_due
            self.status = InvoiceStatus.updated()

    def update_balance(self, amount_paid) -> None:
        """Update the invoice balance after a amount_paid."""
        if not amount_paid:
            return None

        new_amount = self.get_balance() - amount_paid

        if new_amount < 0:
            new_amount = Decimal("0.00")
        self.balance = new_amount
        self._update_status()
        _update_registration_status(self)
        self.save(update_fields=["balance", "status"])

    def clearance_balance(self) -> Decimal:
        """Return the balance under which the invoice status should be paritaly cleared."""
        return self.initial_amount_due - self.initial_forty_percent_due()

    def initial_forty_percent_due(self) -> Decimal:
        """Return 40% of the initial amount due."""
        return self.initial_amount_due * Decimal("0.40")

    def save(self, *args, **kwargs):
        """Ensure the balance is set before saving."""
        self._update_status()
        return super().save(*args, **kwargs)

    @classmethod
    def get_default(cls) -> "Invoice":
        """Return a default invoice for placeholder/student defaults."""
        semester = Semester.get_current_semester()
        return cls.objects.create(
            curriculum_course=CurriculumCourse.get_default(),
            student=Student.get_default(),
            semester=semester,
            initial_amount_due=0,
        )

    class Meta:
        constraints = [
            # Prevent duplicate invoices per student/course/semester combination.
            models.UniqueConstraint(
                fields=["student", "curriculum_course", "semester"],
                name="uniq_invoice_student_course_semester",
            )
        ]


def _update_registration_status(invoice: "Invoice") -> int:
    """Update registration status when the invoice balance change."""
    if not invoice:
        return 0

    cleared_status = RegistrationStatus.cleared()

    if invoice.status_id in {"initial", "updated"}:
        reg_status = RegistrationStatus.pending()
    if invoice.status_id == "settled":
        reg_status = RegistrationStatus.partialy_cleared()
    if invoice.status_id == "cleared":
        reg_status = cleared_status

    return (
        Registration.objects.filter(
            student=invoice.student,
            section__curriculum_course=invoice.curriculum_course,
            section__semester=invoice.semester,
        )
        .exclude(status=cleared_status)
        .update(status=reg_status)
    )
