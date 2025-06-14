"""Constants for scheduling and reservations.

Currently this includes the :class:`StatusReservation` enumeration used to
track the life cycle of a student's reservation of a section."""

from django.db import models


class StatusReservation(models.TextChoices):
    CANCELLED = "cancelled", "Cancelled"
    PAID = "paid", "Paid"
    REQUESTED = "requested", "Requested"
    VALIDATED = "validated", "Validated"
