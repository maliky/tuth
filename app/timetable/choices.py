"""Constants for scheduling."""

from django.db.models import IntegerChoices


class SEMESTER_NUMBER(IntegerChoices):
    FIRST = 1, "First (1)"
    SECOND = 2, "Second (2)"
    VACATION = 3, "Vacation (3)"
    REMEDIAL = 4, "Remedial (4)"


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
    SUNDAY = 7, "Sunday"
