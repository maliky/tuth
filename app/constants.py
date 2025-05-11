CURRICULUM_LEVEL_CHOICES = [
    ("freshman", "Freshman"),
    ("sophomore", "Sophomore"),
    ("junior", "Junior"),
    ("senior", "Senior"),
]

COLLEGE_CHOICES: list[tuple[str, str]] = [
    ("COHS", "College of Health Sciences"),
    ("COAS", "College of Arts and Sciences"),
    ("COED", "College of Education"),
    ("CAFS", "College of Agriculture and Food Sciences"),
    ("COET", "College of Engineering and Technology"),
    ("COBA", "College of Business Administration"),
]
REGISTRATION_STATUS_CHOICES = [
    ("pre_registered", "Pre-registered"),
    ("confirmed", "Confirmed"),
    ("pending_clearance", "Pending Clearance"),
]
STATUS_CHOICES = [
    ("pending", "Pending"),
    ("approved", "Approved"),
    ("adjustments_required", "Adjustments Required"),
    ("rejected", "Rejected"),
]


USER_ROLES = [
    ("Dean", "Dean"),
    ("Chair", "Chair"),
    ("Lecturer", "Lecturer"),
    ("Assistant Professor", "Assistant Professor"),
    ("Associate Professor", "Associate Professor"),
    ("Professor", "Professor"),
    ("Technician", "Technician"),
    ("Lab Technician", "Lab Technician"),
    ("Instructor", "Instructor"),
    ("VPAA", "VPAA"),
    ("Registrar", "Registrar"),
    ("FinancialOfficer", "FinancialOfficer"),
    ("EnrollmentOfficer", "EnrollmentOfficer"),
]
