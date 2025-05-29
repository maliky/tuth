from app.shared.constants import MAX_STUDENT_CREDITS
from django.db import models
from django.utils import timezone
from people.models import StudentProfile
from timetable.models import Section

from app.shared.constants.choices import StatusReservation


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
        if (
            self.status != StatusReservation.CANCELLED
            and not self.section.has_available_seats()
        ):
            raise ValidationError("Section has no available seats.")

        # apply credit-hour rule
        CreditLimitValidator()(self)  # see §2

    def save(self, *args, **kwargs):
        # ⑥ – keep the cache up-to-date
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
        assert self.status != self.Status.CANCELLED, "Reservation already cancelled."
        self.status = self.Status.CANCELLED
        self.save()

    def student_fee(self):
        """get all the section fees, apply the financial aid compute how much the student owe to TU"""
        # > fill in the gap.

    class Meta:
        unique_together = ("student", "section")
