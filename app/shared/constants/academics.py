import re

MAX_STUDENT_CREDITS = 18
COURSE_PATTERN = re.compile(
    r"(?P<dept>[A-Z]{2,4})[_-]?(?P<num>[0-9]{3})(?:\s*-\s*(?P<college>[A-Z]{3,4}))?"
)

COLLEGE_CHOICES: list[tuple[str, str]] = [
    ("COHS", "College of Health Sciences"),
    ("COAS", "College of Arts and Sciences"),
    ("COED", "College of Education"),
    ("CAFS", "College of Agriculture and Food Sciences"),
    ("COET", "College of Engineering and Technology"),
    ("COBA", "College of Business Administration"),
]
