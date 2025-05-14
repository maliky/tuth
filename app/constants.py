OBJECT_PERM_MATRIX = {
    "college": {
        "view": [
            "dean",
            "chair",
            "vpaa",
            "registrar",
            "student",
            "prospective_student",
        ],
        "change": ["dean", "vpaa"],
        "delete": ["vpaa"],
        "add": ["vpaa"],
    },
    "curriculum": {
        "view": [
            "dean",
            "chair",
            "instructor",
            "registrar",
            "vpaa",
            "student",
            "prospective_student",
        ],
        "change": ["dean", "registrar", "vpaa"],
        "delete": ["vpaa"],
        "add": ["dean", "registrar"],
    },
    "course": {
        "view": [
            "dean",
            "chair",
            "instructor",
            "lecturer",
            "registrar",
            "vpaa",
            "student",
            "prospective_student",
        ],
        "change": ["dean", "chair"],
        "delete": ["dean"],
        "add": ["chair", "dean"],
    },
    "section": {
        "view": [
            "dean",
            "chair",
            "instructor",
            "registrar",
            "vpaa",
            "lecturer",
            "student",
        ],
        "change": ["dean", "chair", "registrar"],
        "delete": ["registrar"],
        "add": ["registrar", "chair", "dean"],
    },
    "registration": {
        "view": ["registrar", "enrollment_officer", "vpaa", "student"],
        "change": ["registrar", "enrollment_officer"],
        "delete": ["registrar"],
        "add": ["registrar", "enrollment_officer", "student"],
    },
    "document": {
        "view": [
            "registrar",
            "financial_officer",
            "enrollment_officer",
            "student",
            "prospective_student",
        ],
        "change": ["registrar"],
        "delete": ["registrar"],
        "add": [
            "registrar",
            "enrollment_officer",
            "student",
            "prospective_student",
        ],
    },
    "financialrecord": {
        "view": ["financial_officer", "registrar", "student"],
        "change": ["financial_officer"],
        "delete": [],
        "add": ["financial_officer"],
    },
    "paymenthistory": {
        "view": ["financial_officer", "registrar", "student"],
        "change": ["financial_officer"],
        "delete": [],
        "add": ["financial_officer"],
    },
    "roleassignment": {
        "view": ["dean", "vpaa", "registrar"],
        "change": ["vpaa"],
        "delete": ["vpaa"],
        "add": ["vpaa"],
    },
    "room": {
        "view": [
            "dean",
            "chair",
            "registrar",
            "instructor",
            "student",
            "prospective_student",
        ],
        "change": ["registrar"],
        "delete": ["registrar"],
        "add": ["registrar"],
    },
    "building": {
        "view": [
            "registrar",
            "vpaa",
            "dean",
            "chair",
            "student",
            "prospective_student",
        ],
        "change": ["registrar"],
        "delete": ["vpaa"],
        "add": ["registrar", "vpaa"],
    },
    "academicyear": {
        "view": [
            "vpaa",
            "registrar",
            "dean",
            "chair",
            "student",
            "prospective_student",
        ],
        "change": ["vpaa"],
        "delete": ["vpaa"],
        "add": ["vpaa"],
    },
    "term": {
        "view": [
            "vpaa",
            "registrar",
            "dean",
            "chair",
            "student",
            "prospective_student",
        ],
        "change": ["vpaa", "registrar"],
        "delete": ["vpaa"],
        "add": ["registrar", "vpaa"],
    },
}

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

USER_ROLES: list[str] = [
    "student",
    "prospective_student",
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

DEFAULT_ROLE_TO_COLLEGE = {
    "dean": "COAS",  # map role → default college code
    "chair": "COAS",
    "instructor": "COAS",
    "lecturer": "COAS",
    "assistant_professor": "COAS",
    "associate_professor": "COAS",
    "professor": "COAS",
    "technician": "COAS",
    "lab_technician": "COAS",
    "instructor": "COAS",
}

TEST_PW = "test"
