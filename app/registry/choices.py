"""Constants used by the student registry subsystem.

This module enumerates document types that can be uploaded by students as
well as the possible statuses for both registrations and documents.
"""

from django.db.models import TextChoices


# class GradeChoice(TextChoices):
#     A = "a", "A"
#     AB = "ab", "A"  # Absent
#     B = "b", "B"
#     C = "c", "C"
#     D = "d", "D"
#     DR = "dr", "DR"  # "Section Droped"
#     F = "f", "F"  # " (Failed)"
#     I = "i", "I"  # " (Incomplete)"
#     IP = "ip", "IP"  # " (In Progress)"
#     NG = "ng", "NG"  # " (No Grade)"
#     W = "w", "W"  # " (Semester Withdraw)"


class DocumentType(TextChoices):
    WAEC = "waec", "Waec"
    BILL = "bill", "Bill"
    TRANSCRIPT = "transcript", "Transcript"
    PUBLIC = "public", "Public_signature"


class StatusRegistration(TextChoices):
    PENDING = "pending payment", "Pending Payment"
    FINANCIALLY_CLEARED = "financially_cleared", "Financially_Cleared"
    COMPLETED = "completed", "Completed"
    CANCEL = "cancel", "Cancel"
    REMOVE = "remove", "Remove"
    APPROVED = "approved", "Approved"


class StatusDocument(TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    ADJUSTMENTS_REQUIRED = "adjustments_required", "Adjustments Required"
    REJECTED = "rejected", "Rejected"
