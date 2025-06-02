from django.db import models


class StatusReservation(models.TextChoices):
    CANCELLED = "cancelled", "Cancelled"
    PAID = "paid", "Paid"
    REQUESTED = "requested", "Requested"
    VALIDATED = "validated", "Validated"
