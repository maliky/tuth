"""Reservation module."""

from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import F
from django.utils import timezone

from app.finance.models import FinancialRecord, Payment, SectionFee
from app.shared.constants import (
    MAX_STUDENT_CREDITS,
    TUITION_RATE_PER_CREDIT,
    PaymentMethod,
    StatusReservation,
)
from app.shared.mixins import StatusableMixin
from app.timetable.models.section import Section
from app.timetable.models.validator import CreditLimitValidator

if TYPE_CHECKING:
    from app.people.models.profile import StaffProfile


class Reservation(StatusableMixin, models.Model):
    student = models.ForeignKey(
        "people.StudentProfile",
        on_delete=models.CASCADE,
        related_name="student_reservations",
    )
    section = models.ForeignKey(
        "timetable.Section", on_delete=models.CASCADE, related_name="section_reservations"
    )
    status = models.CharField(
        max_length=30,
        choices=StatusReservation.choices,
        default=StatusReservation.REQUESTED,
    )

    validation_deadline = models.DateTimeField(default=timezone.now() + timedelta(days=2))
    date_requested = models.DateTimeField(default=timezone.now)
    date_validated = models.DateTimeField(blank=True, null=True)

    @property
    def fee_total(self) -> Decimal:
        """Total fee for this reservation (tuition + section fees)."""

        tuition_fee = self.section.course.credit_hours * TUITION_RATE_PER_CREDIT
        additional_fees = SectionFee.objects.filter(section=self.section).aggregate(
            total=models.Sum("amount")
        ).get("total") or Decimal("0.00")

        return tuition_fee + additional_fees

    def __str__(self) -> str:
        return f"{self.student} -> {self.section} ({self.status})"

    def _check_credit_limit(self) -> None:
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
        Sum of *validated* or *requested* sections credit hours for *this* student
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
    def clean(self) -> None:
        """Model-level validation before every save()."""
        super().clean()

        #  validate seat capacity
        if not self.section.has_available_seats():
            self.validate_status([StatusReservation.CANCELLED])

        # apply credit-hour rule, the idea is that we may reuse this elsewhere
        CreditLimitValidator()(self)

    def save(self, *args, **kwargs) -> None:
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # USER-FACING OPERATIONS
    # ------------------------------------------------------------------
    @transaction.atomic
    def validate(self) -> None:
        """Finance / Registrar marks the reservation as validated."""
        if self.status == StatusReservation.VALIDATED:
            raise ValueError("Reservation already validated.")

        self.status = StatusReservation.VALIDATED
        self.full_clean()
        self.save(update_fields=["status", "date_validated"])

    def cancel(self) -> None:
        assert (
            self.status != StatusReservation.CANCELLED
        ), "Reservation already cancelled."
        self.status = StatusReservation.CANCELLED

        self.save(update_fields=["status"])
        Section.objects.filter(pk=self.section_id).update(
            current_registrations=F("current_registrations") - 1
        )

    def mark_paid(self, by_user: "StaffProfile") -> None:
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
