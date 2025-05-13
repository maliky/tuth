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


OBJECT_PERM_MATRIX = {
    "college": {
        "view_college": [
            "dean",
            "chair",
            "vpaa",
            "registrar",
            "student",
            "prospective_student",
        ],
        "change_college": ["dean", "vpaa"],
        "delete_college": ["vpaa"],
        "add_college": ["vpaa"],
    },
    "curriculum": {
        "view_curriculum": [
            "dean",
            "chair",
            "instructor",
            "registrar",
            "vpaa",
            "student",
            "prospective_student",
        ],
        "change_curriculum": ["dean", "registrar", "vpaa"],
        "delete_curriculum": ["vpaa"],
        "add_curriculum": ["dean", "registrar"],
    },
    "course": {
        "view_course": [
            "dean",
            "chair",
            "instructor",
            "lecturer",
            "registrar",
            "vpaa",
            "student",
            "prospective_student",
        ],
        "change_course": ["dean", "chair"],
        "delete_course": ["dean"],
        "add_course": ["chair", "dean"],
    },
    "section": {
        "view_section": [
            "dean",
            "chair",
            "instructor",
            "registrar",
            "vpaa",
            "lecturer",
            "student",
        ],
        "change_section": ["dean", "chair", "registrar"],
        "delete_section": ["registrar"],
        "add_section": ["registrar", "chair", "dean"],
    },
    "registration": {
        "view_registration": ["registrar", "enrollment_officer", "vpaa", "student"],
        "change_registration": ["registrar", "enrollment_officer"],
        "delete_registration": ["registrar"],
        "add_registration": ["registrar", "enrollment_officer", "student"],
    },
    "document": {
        "view_document": [
            "registrar",
            "financial_officer",
            "enrollment_officer",
            "student",
            "prospective_student",
        ],
        "change_document": ["registrar"],
        "delete_document": ["registrar"],
        "add_document": [
            "registrar",
            "enrollment_officer",
            "student",
            "prospective_student",
        ],
    },
    "financialrecord": {
        "view_financialrecord": ["financial_officer", "registrar", "student"],
        "change_financialrecord": ["financial_officer"],
        "delete_financialrecord": [],
        "add_financialrecord": ["financial_officer"],
    },
    "paymenthistory": {
        "view_paymenthistory": ["financial_officer", "registrar", "student"],
        "change_paymenthistory": ["financial_officer"],
        "delete_paymenthistory": [],
        "add_paymenthistory": ["financial_officer"],
    },
    "roleassignment": {
        "view_roleassignment": ["dean", "vpaa", "registrar"],
        "change_roleassignment": ["vpaa"],
        "delete_roleassignment": ["vpaa"],
        "add_roleassignment": ["vpaa"],
    },
    "room": {
        "view_room": [
            "dean",
            "chair",
            "registrar",
            "instructor",
            "student",
            "prospective_student",
        ],
        "change_room": ["registrar"],
        "delete_room": ["registrar"],
        "add_room": ["registrar"],
    },
    "building": {
        "view_building": [
            "registrar",
            "vpaa",
            "dean",
            "chair",
            "student",
            "prospective_student",
        ],
        "change_building": ["registrar"],
        "delete_building": ["vpaa"],
        "add_building": ["registrar", "vpaa"],
    },
    "academicyear": {
        "view_academicyear": [
            "vpaa",
            "registrar",
            "dean",
            "chair",
            "student",
            "prospective_student",
        ],
        "change_academicyear": ["vpaa"],
        "delete_academicyear": ["vpaa"],
        "add_academicyear": ["vpaa"],
    },
    "term": {
        "view_term": [
            "vpaa",
            "registrar",
            "dean",
            "chair",
            "student",
            "prospective_student",
        ],
        "change_term": ["vpaa", "registrar"],
        "delete_term": ["vpaa"],
        "add_term": ["registrar", "vpaa"],
    },
}
