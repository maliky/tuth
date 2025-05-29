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
    "faculty",
    "vpaa",
    "registrar",
    "financial_officer",
    "enrollment_officer",
]

DEFAULT_ROLE_TO_COLLEGE = {
    "dean": "COAS",  # map role → default college code
    "chair": "COAS",
    "lecturer": "COAS",
    "assistant_professor": "COAS",
    "associate_professor": "COAS",
    "professor": "COAS",
    "technician": "COAS",
    "lab_technician": "COAS",
    "faculty": "COAS",
}
