from django.utils import timezone
from django.db import transaction
from django.db.models import F
from app.timetable.models import Reservation, Section
from app.shared.constants import StatusReservation


def cancel_expired_reservations():
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
