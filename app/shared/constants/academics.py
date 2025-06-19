"""Constants used by the :mod:`academics` app.

This module centralizes enumerations and patterns used when working with
academic entities such as :class:`~app.academics.models.Course` or
curricula. It exposes the ``COURSE_PATTERN`` regular expression, maximum
credit load for a student and enumerations for colleges and curriculum
statuses."""

import re
from app.academics.choices import (
    CollegeCodeChoices,
    CollegeLongNameChoices,
    StatusCurriculum,
    CREDIT_NUMBER,
    LEVEL_NUMBER,
)

MAX_STUDENT_CREDITS = 18
COURSE_PATTERN = re.compile(
    r"(?P<dept>[A-Z]{2,4})[_-]?(?P<num>[0-9]{3})(?:\s*-\s*(?P<college>[A-Z]{3,4}))?"
)


