"""Registration module."""

from __future__ import annotations

from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from app.registry.choices import StatusRegistration
from app.shared.mixins import StatusableMixin
from app.timetable.models import Reservation


class Registration(StatusableMixin, models.Model):
    """Enrollment of a student in a course section.

    Example:
        >>> from app.registry.models import Registration
        >>> reg = Registration.objects.create(
        ...     student=student_profile,
        ...     section=section_factory(1),
        ... )
        >>> Reservation.objects.create(
        ...     student=reg.student,
        ...     section=reg.section,
        ... )  # signal sets ``date_latest_reservation``
        >>> reg.refresh_from_db()
        >>> reg.date_latest_reservation is not None
        True

        >>> Registration.objects.create(student=student, section=section)

    Side Effects:
        ``date_latest_reservation`` is updated whenever a
        :class:`~app.timetable.models.Reservation` is saved.
    """

    student = models.ForeignKey(
        "people.Student",
        on_delete=models.CASCADE,
        related_name="student_registrations",
    )
    section = models.ForeignKey(
        "timetable.Section",
        on_delete=models.CASCADE,
        related_name="section_registrations",
    )
    # this is optional and I could get it through the SatusableMixin
    status = models.CharField(
        max_length=30,
        choices=StatusRegistration.choices,
        default=StatusRegistration.PENDING,
    )
    # > to update with reservation date
    # > but what happen if the reservation is canceled.  Keep the field.
    date_latest_reservation = models.DateTimeField(null=True, blank=True)
    date_registered = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "section"],
                name="uniq_registration_student_section",
            )
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.student} – {self.section} -  {self.status}"


@receiver(post_save, sender=Reservation)
def update_latest_reservation(sender, instance, **kwargs):
    """Keep ``date_latest_reservation`` in sync with reservation activity."""
    reg, _ = Registration.objects.get_or_create(
        student=instance.student, section=instance.section
    )
    reg.date_latest_reservation = timezone.now()
    reg.save(update_fields=["date_latest_reservation"])
