"""Constants used by the student registry subsystem.

This module enumerates document types that can be uploaded by students as
well as the possible statuses for both registrations and documents.
"""

from django.db.models import TextChoices


class GradeChoice(TextChoices):
    A = "a", "A"
    AB = "ab", "AB"
    B = "b", "B"
    C = "c", "C"
    D = "d", "D"
    DR = "dr", "DR"
    F = "f", "F"
    I = "i", "I"  # noqa: E741 ambiguous letter name required by grading scale
    IP = "ip", "IP"
    NG = "ng", "NG"
    W = "w", "W"


# STATUS_CHOICES = list(
#     set(list(DocumentStatus.choices) + list(StatusRegistration.choices))
# )
