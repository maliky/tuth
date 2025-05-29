from app.finance.models import Payment, FinancialRecord
from app.shared.mixins import StatusableMixin
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone
from people.models import StudentProfile
from timetable.models import Section

from app.shared.constants import MAX_STUDENT_CREDITS
from app.shared.constants.choices import StatusReservation
from app.timetable.models.validator import CreditLimitValidator


class Reservation(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE)
    section = models.ForeignKey(Section, on_delete=models.CASCADE)
    status = models.CharField(
        max_length=30,
        choices=StatusReservation.choices,
        default=StatusReservation.REQUESTED,
    )

    date_requested = models.DateTimeField(default=timezone.now)
    date_validated = models.DateTimeField(blank=True, null=True)

    credit_hours_cache = models.PositiveSmallIntegerField(
        editable=False, null=True, help_text="Snapshot of credit hours at save-time"
    )  # <-- ②

    def __str__(self):
        return f"{self.student} -> {self.section} ({self.status})"

    def _check_credit_limit(self):
        prospective = self.credit_hours() + self.section.course.credit_hours
        if prospective > MAX_STUDENT_CREDITS:
            raise ValidationError(
                f"Credit limit exceeded ({prospective}/{MAX_STUDENT_CREDITS})."
            )

    # ------------------------------------------------------------------
    # BUSINESS HELPERS
    # ------------------------------------------------------------------
    def credit_hours(self) -> int:  # <-- ③
        """
        Sum of *validated* or *requested* sections for *this* student
        (excludes cancelled reservations).
        """
        return (
            Reservation.objects.filter(
                student=self.student,
                status__in=[
                    StatusReservation.REQUESTED,
                    StatusReservation.VALIDATED,
                ],
            )
            .aggregate(total=models.Sum("section__course__credit_hours"))
            .get("total")
            or 0
        )

    # ------------------------------------------------------------------
    # LIFE-CYCLE OVERRIDES
    # ------------------------------------------------------------------
    def clean(self):
        """Model-level validation before every save()."""
        super().clean()

        #  validate seat capacity
        if not self.section.has_available_seats():
            StatusableMixin.validate_state(self, [StatusReservation.CANCELLED])

        # apply credit-hour rule
        CreditLimitValidator()(self)

    def save(self, *args, **kwargs):
        self.credit_hours_cache = self.credit_hours()
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # USER-FACING OPERATIONS
    # ------------------------------------------------------------------
    @transaction.atomic
    def validate(self):
        """Finance / Registrar marks the reservation as validated."""
        if self.status == StatusReservation.VALIDATED:
            raise ValueError("Reservation already validated.")

        self.status = StatusReservation.VALIDATED
        self.full_clean()
        self.save(update_fields=["status", "credit_hours_cache", "date_validated"])

    def cancel(self):
        assert (
            self.status != self.StatusReservation.CANCELLED
        ), "Reservation already cancelled."
        self.status = self.StatusReservation.CANCELLED
        self.save()

    def student_fee(self):
        """get all the section fees, apply the financial aid compute how much the student owe to TU"""
        # > fill in the gap.

    def mark_paid(self, by_user):
        """Record payment and mark reservation as paid."""

        if self.status == StatusReservation.PAID:
            raise ValueError("Reservation already paid.")

        Payment.objects.create(
            reservation=self,
            amount=self.fee_total,
            method=PaymentMethod.CASH,
            recorded_by=by_user,
        )

        fr, _ = FinancialRecord.objects.get_or_create(
            student=self.student, defaults={"total_due": Decimal("0.00")}
        )
        # > we may have something to do here if the student is on scholarship 28/05/25
        fr.total_paid = (fr.total_paid or Decimal("0.00")) + self.fee_total
        fr.save(update_fields=["total_paid"])

        self.status = StatusReservation.PAID
        self.save(update_fields=["status"])

    class Meta:
        unique_together = ("student", "section")
