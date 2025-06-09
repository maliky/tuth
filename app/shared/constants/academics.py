"""Academics module."""

from django.db import models
import re

MAX_STUDENT_CREDITS = 18
COURSE_PATTERN = re.compile(
    r"(?P<dept>[A-Z]{2,4})[_-]?(?P<num>[0-9]{3})(?:\s*-\s*(?P<college>[A-Z]{3,4}))?"
)


class CollegeCodeChoices(models.TextChoices):
    COHS = "cohs", "COHS"
    COAS = "coas", "COAS"
    COED = "coed", "COED"
    CAFS = "cafs", "CAFS"
    COET = "coet", "COET"
    COBA = "coba", "COBA"


class CollegeLongNameChoices(models.TextChoices):
    COHS = "cohs_long_name", "College of Health Sciences"
    COAS = "coas_long_name", "College of Arts and Sciences"
    COED = "coed_long_name", "College of Education"
    CAFS = "cafs_long_name", "College of Agriculture and Food Sciences"
    COET = "coet_long_name", "College of Engineering and Technology"
    COBA = "coba_long_name", "College of Business Administration"


class StatusCurriculum(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    NEEDS_REVISION = "needs_revision", "Needs Revision"
