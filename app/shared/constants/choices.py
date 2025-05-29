from django.db import models

APPROVED: str = "approved"
UNDEFINED_CHOICES: str = "undefined_choice"


CLEARANCE_CHOICES: list[str] = ["pending", "cleared", "blocked"]

COLLEGE_CHOICES: list[tuple[str, str]] = [
    ("COHS", "College of Health Sciences"),
    ("COAS", "College of Arts and Sciences"),
    ("COED", "College of Education"),
    ("CAFS", "College of Agriculture and Food Sciences"),
    ("COET", "College of Engineering and Technology"),
    ("COBA", "College of Business Administration"),
]

DOCUMENT_TYPES: list[str] = [
    "waec",
    "bill",
    "transcript",
]


class StatusReservation(models.TextChoices):
    REQUESTED = "requested", "Requested"
    VALIDATED = "validated", "Validated"
    CANCELLED = "cancelled", "Cancelled"


class StatusRegistration(models.TextChoices):
    PENDING = "pending payment", "Pending Payment"
    FINANCIALY_CLEARED = "financialy_cleared", "Financialy_Cleared"    
    COMPLETED = "completed", "Completed"    
    APPROVED = "approved", "Approved"


# la séparation par classe me permet de vérifier la validité des états
# au moment de la sauvegarde ou des modification du code.
# > TODO : rewrite below as several models.TextChoices and update correponding models and calls.
STATUS_CHOICES_PER_MODEL: dict[str, list[str]] = {
    "curriculum": [
        "pending",
        "approved",
        "needs_revision",
    ],
    "document": [
        "pending",
        "approved",
        "adjustments_required",
        "rejected",
    ],
}

STATUS_CHOICES: list[str] = list(
    set([c for choices in STATUS_CHOICES_PER_MODEL.values() for c in choices])
)
