"""Choices module for academic package."""

from django.db import models
from django.db.models import IntegerChoices


class DepartmentShortNameChoice(models.TextChoices):
    ACCT = "ACCT", "ACCT"
    AGR = "AGR", "AGR"
    BFIN = "BFIN", "BFIN"
    BIO = "BIO", "BIO"
    BUS = "BUS", "BUS"
    BUSA = "BUSA", "BUSA"
    CENG = "CENG", "CENG"
    CHE = "CHE", "CHE"
    CHEM = "CHEM", "CHEM"
    CSE = "CSE", "CSE"
    CSENG = "CSENG", "CSENG"
    ECD = "ECD", "ECD"
    ECON = "ECON", "ECON"
    EDU = "EDU", "EDU"
    EDUP = "EDUP", "EDUP"
    EED = "EED", "EED"
    EEDU = "EEDU", "EEDU"
    EENG = "EENG", "EENG"
    ENGL = "ENGL", "ENGL"
    ENVS = "ENVS", "ENVS"
    FREN = "FREN", "FREN"
    GCED = "GCED", "GCED"
    GENG = "GENG", "GENG"
    GLE = "GLE", "GLE"
    HIST = "HIST", "HIST"
    HSC = "HSC", "HSC"
    HSM = "HSM", "HSM"
    MATH = "MATH", "MATH"
    MENG = "MENG", "MENG"
    MID = "MID", "MID"
    MIDW = "MIDW", "MIDW"
    NUR = "NUR", "NUR"
    PADM = "PADM", "PADM"
    PE = "PE", "PE"
    PH = "PH", "PH"
    PHIL = "PHIL", "PHIL"
    PHYS = "PHYS", "PHYS"
    PSY = "PSY", "PSY"
    DEFT = "DEFT", "DEFT"  # Default


class DepartmentLongNameChoice(models.TextChoices):
    ACCT = "acct_long_name", "Accounting Department"
    AGR = "agr_long_name", "Agriculture Department"
    BFIN = "bfin_long_name", "Fincance Department"
    BIO = "bio_long_name", "Biologie Department"
    BUS = "bus_long_name", "Business Department"
    BUSA = "busa_long_name", "Admninistration Department"
    CENG = "ceng_long_name", "Civil Engineering Department"
    CHE = "che_long_name", "Chemistry1 Department"
    CHEM = "chem_long_name", "Chemistry2 Department"
    CSE = "cse_long_name", "Computer Science Department"
    CSENG = "cseng_long_name", "Computer Science 2 Department"
    ECD = "ecd_long_name", "ECD Department"
    ECON = "econ_long_name", "Economy Department"
    EDU = "edu_long_name", "EDU Department"
    EDUP = "edup_long_name", "EDUP Department"
    EED = "eed_long_name", "EED Department"
    EEDU = "eedu_long_name", "EEDU Department"
    EENG = "eeng_long_name", "English 1 Department"
    ENGL = "engl_long_name", "English 2 Department"
    ENVS = "envs_long_name", "Environmental Sciences Department"
    FREN = "fren_long_name", "French Department"
    GCED = "gced_long_name", "Grebo Department"
    GENG = "geng_long_name", "General Engineering Department"
    GLE = "gle_long_name", "Grebo 2 Department"
    HIST = "hist_long_name", "History 2 Department"
    HSC = "hsc_long_name", "HSC Department"
    HSM = "hsm_long_name", "HSM Department"
    MATH = "math_long_name", "Mathematics Department"
    MENG = "meng_long_name", "MENG Department"
    MID = "mid_long_name", "Midwifery 1 Department"
    MIDW = "midw_long_name", "Midwifery 2 Department"
    NUR = "nur_long_name", "Nursing Department"
    PADM = "padm_long_name", "Public Administration Department"
    PE = "pe_long_name", "Physical Education Department"
    PH = "ph_long_name", "PH Department"
    PHIL = "phil_long_name", "Philosophy Department"
    PHYS = "phys_long_name", "Physic Department"
    PSY = "psy_long_name", "Psychology Department"
    DEFT = "deft_long_name", "Default Department"  # default


class CollegeCodeChoices(models.TextChoices):
    COHS = "COHS", "COHS"
    COAS = "COAS", "COAS"
    COED = "COED", "COED"
    CAFS = "CAFS", "CAFS"
    COET = "COET", "COET"
    COBA = "COBA", "COBA"
    DEFT = "DEFT", "DEFT"  # default
    TEST = "TEST", "TEST"  # for test purposes


class CollegeLongNameChoices(models.TextChoices):
    COHS = "cohs_long_name", "College of Health Sciences"
    COAS = "coas_long_name", "College of Arts and Sciences"
    COED = "coed_long_name", "College of Education"
    CAFS = "cafs_long_name", "College of Agriculture and Food Sciences"
    COET = "coet_long_name", "College of Engineering and Technology"
    COBA = "coba_long_name", "College of Business Administration"
    DEFT = (
        "deft_long_name",
        "College of default when no other college is chosen.",
    )  # default
    TEST = "test_long_name", "College used for Test purposes"  # for test purposes

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
    FIVE = 5, "5"
    SIX = 6, "6"
    SEVEN = 7, "7"
    EIGHT = 8, "8"
    NINE = 9, "9"
    TEN = 10, "10"
    TBA = 99, "99"  # to be attributed


class LEVEL_NUMBER(IntegerChoices):
    ONE = 1, "freshman"
    TWO = 2, "sophomore"
    THREE = 3, "junior"
    FOUR = 4, "senior"
    FIVE = 5, "senior"
    UNDEF = 99, "undefined"  # undefined
