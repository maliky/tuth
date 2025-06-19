from django.db import models
from django.db.models import IntegerChoices

class StatusReservation(models.TextChoices):
    CANCELLED = "cancelled", "Cancelled"
    PAID = "paid", "Paid"
    REQUESTED = "requested", "Requested"
    VALIDATED = "validated", "Validated"


class SEMESTER_NUMBER(IntegerChoices):
    FIRST = 1, "First"
    SECOND = 2, "Second"
    VACATION = 3, "Vacation"
    REMEDIAL = 4, "Remedial"


class TERM_NUMBER(IntegerChoices):
    FIRST = 1, "First"
    SECOND = 2, "Second"


class WEEKDAYS_NUMBER(IntegerChoices):
    """Integer representation of weekdays."""

    TBA = 0, "TBA"
    MONDAY = 1, "Monday"
    TUESDAY = 2, "Tuesday"
    WEDNESDAY = 3, "Wednesday"
    THURSDAY = 4, "Thursday"
    FRIDAY = 5, "Friday"
    SATURDAY = 6, "Saturday"
