"""Finance invoice models."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.db import models
from django.db.models import Sum
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from simple_history.models import HistoricalRecords

from app.finance.models.status_types_methods import InvoiceStatus, Payer
from app.registry.models.registration import Registration
from app.registry.models.status_types import RegistrationStatus
from app.shared.mixins import StatusableMixin

PAYER_STUDENT_CODE = "student"
PAYER_GOV_CODE = "gov"
PAYER_MIXED_CODE = "mixed"


def _quantize_money(value: Decimal) -> Decimal:
    """Normalize decimal amounts to two places."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _clamp_non_negative(value: Decimal) -> Decimal:
    """Ensure decimal amounts do not go below zero."""
    if value < Decimal("0.00"):
        return Decimal("0.00")
    return value


def _ensure_payer_dfts() -> None:
    """Ensure payer lookup values exist before invoice writes."""
    Payer._populate_attributes_and_db()


class StdSemesterInvoice(StatusableMixin, models.Model):
    """Parent invoice level for one student and one semester."""

    student = models.ForeignKey(
        "people.Student",
        on_delete=models.PROTECT,
        related_name="student_semester_invoices",
    )
    semester = models.ForeignKey(
        "timetable.Semester",
        on_delete=models.PROTECT,
        related_name="student_semester_invoices",
    )
    fee_stacks = models.ManyToManyField(
        "finance.FeeStack",
        related_name="student_semester_invoices",
        blank=True,
    )
    course_tuition_payer = models.ForeignKey(
        "finance.Payer",
        on_delete=models.PROTECT,
        related_name="student_semester_invoices_for_tuition",
        default=PAYER_GOV_CODE,
    )
    fee_payer = models.ForeignKey(
        "finance.Payer",
        on_delete=models.PROTECT,
        related_name="student_semester_invoices_for_fees",
        default=PAYER_STUDENT_CODE,
    )
    required_deposit_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("40.00"),
    )
    required_deposit_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    initial_amount_due = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    balance = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.ForeignKey(
        "finance.InvoiceStatus",
        on_delete=models.PROTECT,
        related_name="student_semester_invoices",
        default="initial",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.student} - {self.semester}"

    def get_balance(self) -> Decimal:
        """Return balance with a non-null runtime fallback."""
        if self.balance is None:
            self.balance = self.initial_amount_due
        return self.balance

    def initial_required_deposit(self) -> Decimal:
        """Return the required deposit amount using the current percent."""
        percent = Decimal(self.required_deposit_percent or Decimal("0.00")) / Decimal(
            "100.00"
        )
        return _quantize_money(self.initial_amount_due * percent)

    def initial_forty_percent_due(self) -> Decimal:
        """Compatibility alias for shared admin amount-due filter."""
        return self.initial_required_deposit()

    def clearance_balance(self) -> Decimal:
        """Return the balance threshold for a settled status."""
        return _clamp_non_negative(
            self.initial_amount_due - self.initial_required_deposit()
        )

    def _update_status(self) -> None:
        """Update parent invoice status from the current balance."""
        balance = self.get_balance()
        if balance == self.initial_amount_due:
            self.status = InvoiceStatus.initial()
        elif balance == Decimal("0.00"):
            self.status = InvoiceStatus.cleared()
        elif balance <= self.clearance_balance():
            self.status = InvoiceStatus.settled()
        else:
            self.status = InvoiceStatus.updated()

    def _resolved_fee_line_payers(self) -> set[str]:
        """Resolve payer set from attached fee stacks for this semester."""
        from app.finance.models.fee_stack import resolve_fee_stack_line_payers

        return resolve_fee_stack_line_payers(
            fee_stacks=list(self.fee_stacks.all()),
            semester=self.semester,
            fallback_payer=self.fee_payer_id,
        )

    def _refresh_crs_invoice_balances(self, course_total: Decimal) -> None:
        """Propagate parent balance/status to child course invoices."""
        child_invoices = list(self.course_invoices.all().select_related("status"))
        if not child_invoices:
            return
        if self.initial_amount_due <= Decimal("0.00") or course_total <= Decimal("0.00"):
            course_balance_total = Decimal("0.00")
        else:
            course_balance_total = _quantize_money(
                self.get_balance() * (course_total / self.initial_amount_due)
            )
        remaining_balance = _clamp_non_negative(course_balance_total)
        for index, child_invoice in enumerate(child_invoices):
            if index == len(child_invoices) - 1:
                child_balance = _clamp_non_negative(remaining_balance)
            else:
                child_balance = min(child_invoice.initial_amount_due, remaining_balance)
            remaining_balance = _clamp_non_negative(remaining_balance - child_balance)
            child_invoice.balance = child_balance
            child_invoice._update_status()
            CourseInvoice.objects.filter(pk=child_invoice.pk).update(
                balance=child_invoice.balance,
                status_id=child_invoice.status_id,
            )
            _update_registration_status(child_invoice)

    def refresh_totals_from_sources(self, save_model: bool = True) -> None:
        """Recompute totals from child invoices, fee stacks, and payments."""
        course_total = self.course_invoices.aggregate(
            total=Sum("initial_amount_due")
        ).get("total") or Decimal("0.00")
        semester_fee_total = sum(
            (
                fee_stack.total_amount_for_semester(self.semester)
                for fee_stack in self.fee_stacks.all()
            ),
            Decimal("0.00"),
        )
        self.initial_amount_due = _quantize_money(course_total + semester_fee_total)
        self.required_deposit_amount = self.initial_required_deposit()

        # Pending payments are informational and do not reduce due amounts.
        payments_total = self.payments.filter(status_id="cleared").aggregate(
            total=Sum("amount_paid")
        ).get("total") or Decimal("0.00")
        self.balance = _clamp_non_negative(self.initial_amount_due - payments_total)

        resolved_payers = self._resolved_fee_line_payers()
        if len(resolved_payers) > 1:
            self.fee_payer_id = PAYER_MIXED_CODE
        elif len(resolved_payers) == 1:
            self.fee_payer_id = resolved_payers.pop()
        elif not self.fee_payer_id:
            self.fee_payer_id = PAYER_STUDENT_CODE
        self._update_status()
        self._refresh_crs_invoice_balances(course_total)

        if save_model:
            self.save(
                update_fields=[
                    "initial_amount_due",
                    "required_deposit_amount",
                    "balance",
                    "fee_payer",
                    "status",
                ]
            )

    def save(self, *args, **kwargs):
        """Keep monetary fields initialized before persisting."""
        _ensure_payer_dfts()
        if self.balance is None:
            self.balance = self.initial_amount_due
        self.required_deposit_amount = self.initial_required_deposit()
        self._update_status()
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "semester"],
                name="uniq_student_semester_invoice",
            )
        ]
        ordering = ["-semester__start_date", "student__student_id"]
        verbose_name = "Student semester invoice"
        verbose_name_plural = "Student semester invoices"


class CourseInvoice(StatusableMixin, models.Model):
    """Course-level invoice attached to a student and semester."""

    curriculum_course = models.ForeignKey(
        "academics.CurriCourse", on_delete=models.CASCADE
    )
    student = models.ForeignKey("people.Student", on_delete=models.PROTECT)
    semester = models.ForeignKey("timetable.Semester", on_delete=models.PROTECT)
    student_semester_invoice = models.ForeignKey(
        "finance.StdSemesterInvoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="course_invoices",
    )
    initial_amount_due = models.DecimalField(max_digits=8, decimal_places=2)
    status = models.ForeignKey(
        "finance.InvoiceStatus",
        on_delete=models.PROTECT,
        related_name="course_invoices",
        default="initial",
    )
    balance = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    history = HistoricalRecords()
    created_at = models.DateTimeField(auto_now_add=True)
    recorded_by = models.ForeignKey(
        "people.Staff",
        null=True,
        on_delete=models.SET_NULL,
    )
    scholarship = models.ForeignKey(
        "finance.scholarship", on_delete=models.PROTECT, null=True, blank=True
    )

    def get_balance(self) -> Decimal:
        """Return balance with a non-null runtime fallback."""
        if self.balance is None:
            self.balance = self.initial_amount_due
        return self.balance

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.curriculum_course} - {self.balance}"

    def _update_status(self) -> None:
        """Update status from course invoice balance."""
        balance = self.get_balance()
        if balance == self.initial_amount_due:
            self.status = InvoiceStatus.initial()
        elif balance == Decimal("0.00"):
            self.status = InvoiceStatus.cleared()
        elif balance <= self.clearance_balance():
            self.status = InvoiceStatus.settled()
        else:
            self.status = InvoiceStatus.updated()

    def update_balance(self, amount_paid) -> None:
        """Update course-invoice balance and refresh parent totals."""
        if not amount_paid:
            return None

        self.balance = _clamp_non_negative(self.get_balance() - Decimal(amount_paid))
        self._update_status()
        _update_registration_status(self)
        self.save(update_fields=["balance", "status"])
        parent_invoice = self.student_semester_invoice
        if parent_invoice is not None:
            parent_invoice.refresh_totals_from_sources(save_model=True)

    def clearance_balance(self) -> Decimal:
        """Return balance under which the invoice is considered settled."""
        return self.initial_amount_due - self.initial_forty_percent_due()

    def initial_forty_percent_due(self) -> Decimal:
        """Return 40% of the initial amount due."""
        amount_due: Decimal | None = getattr(self, "initial_amount_due", None)
        if amount_due is None:
            amount_due = self.balance
        if amount_due is None:
            return Decimal("0.00")
        return amount_due * Decimal("0.40")

    def _ensure_parent_invoice(self) -> None:
        """Attach a parent student-semester invoice when missing."""
        if self.student_semester_invoice_id:
            return
        if not self.student_id or not self.semester_id:
            return
        _ensure_payer_dfts()
        parent_invoice, _ = StdSemesterInvoice.objects.get_or_create(
            student_id=self.student_id,
            semester_id=self.semester_id,
        )
        self.student_semester_invoice = parent_invoice

    def save(self, *args, **kwargs):
        """Ensure defaults and parent linkage before saving."""
        initial_amount_due: Decimal | None = getattr(self, "initial_amount_due", None)
        if initial_amount_due is None:
            if self.balance is not None:
                self.initial_amount_due = self.balance
            else:
                self.initial_amount_due = Decimal("0.00")
        if self.balance is None:
            self.balance = self.initial_amount_due
        self._ensure_parent_invoice()
        self._update_status()
        save_result = super().save(*args, **kwargs)
        parent_invoice = self.student_semester_invoice
        if parent_invoice is not None:
            parent_invoice.refresh_totals_from_sources(save_model=True)
        return save_result

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "curriculum_course", "semester"],
                name="uniq_invoice_student_course_semester",
            )
        ]
        db_table = "finance_courseinvoice"
        verbose_name = "Course invoice"
        verbose_name_plural = "Course invoices"


# Backward-compatible import alias kept temporarily while other modules migrate.
Invoice = CourseInvoice


@receiver(m2m_changed, sender=StdSemesterInvoice.fee_stacks.through)
def refresh_parent_invoice_after_fee_stack_change(
    sender, instance, action, **kwargs
) -> None:
    """Refresh parent totals when fee-stack links are changed."""
    if action in {"post_add", "post_remove", "post_clear"}:
        instance.refresh_totals_from_sources(save_model=True)


def _update_registration_status(invoice: "CourseInvoice") -> int:
    """Update registration status when the course-invoice status changes."""
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
