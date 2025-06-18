"""Background tasks for the timetable application.

This module houses operations that are typically run in the background,
such as periodic cleanup of expired reservations.
"""

from django.utils import timezone
from django.db import transaction
from django.db.models import F
from app.timetable.models import Reservation, Section
from app.shared.constants import StatusReservation


def cancel_expired_reservations():
    """Cancel reservations that were not validated before their deadline.

    Reservations past their validation deadline are marked as cancelled.
    Updates to reservation and section records occur inside a database
    transaction to keep counts consistent.
    """

    now = timezone.now()
    expired_reservations = Reservation.objects.filter(
        status=StatusReservation.REQUESTED, validation_deadline__lt=now
    )

    with transaction.atomic():
        for reservation in expired_reservations.select_related("section"):
            reservation.status = StatusReservation.CANCELLED
            reservation.save(update_fields=["status"])

            Section.objects.filter(pk=reservation.section.pk).update(
                current_registrations=F("current_registrations") - 1
            )
