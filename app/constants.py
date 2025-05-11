APPROVED: str = "approved"  # keep in one constants module if you wish

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
REGISTRATION_STATUS_CHOICES: list[str] = [
    "pre_registered",
    "confirmed",
    "pending_clearance",
]

# la séparation par classe me permet de vérifier la validité des états
# au moment de la sauvegarde ou des modification du code.
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

USER_ROLES: list[str] = [
    "dean",
    "chair",
    "lecturer",
    "assistant_professor",
    "associate_professor",
    "professor",
    "technician",
    "lab_technician",
    "instructor",
    "vpaa",
    "registrar",
    "financial_officer",
    "enrollment_officer",
]
