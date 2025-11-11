"""Constants used by the :mod:academics app.

It exposes the COURSE_PATTERN regular expression, maximum
credit load for a student and enumerations for colleges and curriculum
statuses.
"""

import re

MAX_STUDENT_CREDITS = 18
COURSE_PATTERN = re.compile(
    r"(?:(?P<college>[A-Z]{3,4})-)?(?P<dept>[A-Z]{2,4})[_-]?(?P<num>[0-9]{3})"
)
