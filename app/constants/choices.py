# app/constants/choices.py
from django.db.models import IntegerChoices


class SEMESTER_NUMBER(IntegerChoices):
    FIRST = 1, "First"
    SECOND = 2, "Second"
    VACATION = 3, "Vacation"
    REMEDIAL = 4, "Remedial"


class TERM_NUMBER(IntegerChoices):
    FIRST = 1, "First"
    SECOND = 2, "Second"


class CreditChoices(IntegerChoices):
    ONE = 1, "1"
    TWO = 2, "2"
    THREE = 3, "3"
    FOUR = 4, "4"
    SiX = 6, "6"
    TEN = 10, "10"


APPROVED: str = "approved"
UNDEFINED_CHOICES: str = "undefined_choice"

CURRICULUM_LEVEL_CHOICES: list[str] = [
    "freshman",
    "sophomore",
    "junior",
    "senior",
]
CLEARANCE_CHOICES: list[str] = [
    "pending",
    "cleared",
    "blocked",
]
COLLEGE_CHOICES: list[tuple[str, str]] = [
    ("COHS", "College of Health Sciences"),
    ("COAS", "College of Arts and Sciences"),
    ("COED", "College of Education"),
    ("CAFS", "College of Agriculture and Food Sciences"),
    ("COET", "College of Engineering and Technology"),
    ("COBA", "College of Business Administration"),
]

# la séparation par classe me permet de vérifier la validité des états
# au moment de la sauvegarde ou des modification du code.
STATUS_CHOICES_PER_MODEL: dict[str, list[str]] = {
    "registration": [
        "pre_registered",
        "approved",
        "pending",
    ],
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
