"""Payment module."""

from __future__ import annotations

from decimal import Decimal

from django.db import models
from simple_history.models import HistoricalRecords

from app.academics.models.course import CurriculumCourse
from app.people.models.student import Student
from app.shared.admin.core import get_current_semester
from app.shared.status.mixins import StatusableMixin


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
        >>> from app.academics.models.course import CurriculumCourse
        >>> from app.people.models.student import Student
        >>> from app.shared.admin.core import get_current_semester
        >>> Invoice.objects.create(
        ...     curriculum_course=CurriculumCourse.get_default(),
        ...     student=Student.get_default(),
        ...     semester=get_current_semester(),
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

    balance = models.DecimalField(max_digits=8, decimal_places=2)
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

    def __str__(self) -> str:  # pragma: no cover
        """Return a concise representation of the payment."""
        return f"{self.curriculum_course} - {self.balance}"

    def _ensure_balance(self) -> None:
        """Set the balance on first save when not provided."""
        if self.balance is None:
            self.balance = self.initial_amount_due

    def _update_status(self) -> None:
        """Update the invoice status based on balance."""
        self._ensure_balance()
        if self.balance == self.initial_amount_due:
            self.status = "initial"
        elif self.balance == 0:
            self.status = "cleared"
        elif self.balance <= self.clearance_balance():
            self.status = "settled"
        else:
            # self.clearance_balance() < self.balance < self.initial_amount_due
            self.status = "updated"

    def update_balance(self,amount_paid):
        """Update the invoice balance after a amount_paid"""
        new_amount = self.invoice.balance - self.amount_paid
        if new_amount < 0:
            new_amount = Decimal("0.00")
        self.invoice.balance = new_amount
        self.invoice.save(update_fields=["balance"])

    def clearance_balance(self) -> Decimal:
        """Return the balance under which the invoice status should be paritaly cleared."""
        return self.initial_amount_due - self.initial_forty_percent_due()

    def initial_forty_percent_due(self) -> Decimal:
        """Return 40% of the initial amount due."""
        return self.initial_amount_due * Decimal("0.40")

    def save(self, *args, **kwargs) -> None:
        """Ensure the balance is set before saving."""

        # > will this be method be called on update_field ?
        self._update_status()
        return super().save(*args, **kwargs)

    @classmethod
    def get_default(cls) -> "Invoice":
        """Return a default invoice for placeholder/student defaults."""
        semester = get_current_semester()
        return cls.objects.create(
            curriculum_course=CurriculumCourse.get_default(),
            student=Student.get_default(),
            semester=semester,
            initial_amount_due=0,
            balance=0,
        )

    class Meta:
        constraints = [
            # Prevent duplicate invoices per student/course/semester combination.
            models.UniqueConstraint(
                fields=["student", "curriculum_course", "semester"],
                name="uniq_invoice_student_course_semester",
            )
        ]
