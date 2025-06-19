"""Choices module for academic package."""

from django.db import models
from django.db.models import IntegerChoices


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


class CREDIT_NUMBER(IntegerChoices):
    ZERO = 0, "0"
    ONE = 1, "1"
    TWO = 2, "2"
    THREE = 3, "3"
    FOUR = 4, "4"
    SIX = 6, "6"
    TEN = 10, "10"


class LEVEL_NUMBER(IntegerChoices):
    ONE = 1, "freshman"
    TWO = 2, "sophomore"
    THREE = 3, "junior"
    FOUR = 4, "senior"
    FIVE = 5, "senior"
