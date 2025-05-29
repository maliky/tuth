APPROVED: str = "approved"
UNDEFINED_CHOICES: str = "undefined_choice"

CLEARANCE_CHOICES: list[str] = ["pending", "cleared", "blocked"]


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
