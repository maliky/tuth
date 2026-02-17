"""Choices module for academic package."""

from django.db.models import IntegerChoices, TextChoices


class DptShortNameChoice(TextChoices):
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


class DptLongNameChoice(TextChoices):
    ACCT = "acct_long_name", "Accounting Department"
    AGR = "agr_long_name", "Agriculture Department"
    BFIN = "bfin_long_name", "Finance Department"
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


COLLEGE_CODE = {
    # standard
    "cohs": "COHS",
    "coas": "COAS",
    "coed": "COED",
    "cfas": "CAFS",
    "cafs": "CAFS",
    "coet": "COET",
    "coba": "COBA",
    "coab": "COBA",
    "deft": "DEFT",
    "test": "TEST",
    "": "DEFT",
    # legacy
    "cba": "COBA",
    "chs": "COHS",
    "edrce": "COED",
    "cet": "COET",
    "cas": "COAS",
}

COLLEGE_LONG_NAME = {
    "cohs": "College of Health Sciences",
    "coas": "College of Arts and Sciences",
    "coed": "College of Education",
    "cafs": "College of Agriculture and Food Sciences",
    "coet": "College of Engineering and Technology",
    "coba": "College of Business Administration",
    "deft": "Default College",
    "test": "College used for Test purposes",  # for test purposes,
}


class LEVEL_NUMBER(IntegerChoices):
    ONE = 1, "freshman"
    TWO = 2, "sophomore"
    THREE = 3, "junior"
    FOUR = 4, "senior"
    FIVE = 5, "senior"
    UNDEF = 99, "undefined"  # undefined


# this translate UM_registrations.Major EnrollType? to standard curriculum
# this translate UM_Crss.CrsCode/Course to a standard curriculum.
# this translate UM_Registration.Major/Enrolltype to a standard curriculum.
LEGACY_CURRICULUM_MAP = {
    "": "WVSTU - GEN",  # empty major → default to university-wide general
    "AA - Applied  Science": "WVSTU - GEN",
    "AA- Applied  Science": "WVSTU - GEN",
    "AA- Applied Science": "WVSTU - GEN",
    "ACCOUNTING": "BBA - Accounting",
    "ACCT": "BBA - Accounting",
    "AGR": "BS - Agro",
    "Accounting 1": "BBA - Accounting",
    "Agriculture 1": "BS - Agri",
    "Agriculture 2": "BS - Agro",
    "Arts in Economics 1": "BS - Economics",
    "BA - 2ndEd/Biology": "BA - 2ndEd/Biology",
    "BA - 2ndEd/Chem Phys": "BA - 2ndEd/Chemistry",
    "BA - 2ndEd/Chemistry": "BA - 2ndEd/Chemistry",
    "BA - 2ndEd/Eng Lit": "BA - 2ndEd/Eng Lit",
    "BA - 2ndEd/History": "BA - 2ndEd/History",
    "BA - 2ndEd/Math": "BA - 2ndEd/Math",
    "BA - ECD": "BA - Early Child Dev",
    "BA - Economics": "BS - Economics",
    "BA - English": "BA - 2ndEd/Eng Lit",
    "BA - Guidance Coun": "BA - Guidance Counseling",
    "BA - History": "BA - 2ndEd/History",
    "BA - Primary Ed": "BA - Primary Ed",
    "BA - Psychology": "BA - Psychology",
    "BA-BIOLOGY": "BA - 2ndEd/Biology",
    "BA-CHEMISTRY": "BA - 2ndEd/Chemistry",
    "BA-ECD": "BA - Early Child Dev",
    "BA-ENGL/LIT": "BA - 2ndEd/Eng Lit",
    "BA-GUIDANCE/COUNS": "BA - Guidance Counseling",
    "BA-HISTORY": "BA - 2ndEd/History",
    "BA-MATHEMATICS": "BA - 2ndEd/Math",
    "BA-PRIMARY EDUCATION": "BA - Primary Ed",
    "BBA - Accounting": "BBA - Accounting",
    "BBA - Banking & Fin": "BBA - Banking & Finance",
    "BBA - Business Admin": "BBA - Management",
    "BBA Business Admin": "BBA - Management",
    "BFIN": "BBA - Banking & Finance",
    "BFN": "BBA - Banking & Finance",
    "BPA - Public Admin": "BPA - Management",
    "BSCE - Civil Eng": "BS - Civil Eng",
    "BSEE - Elec Eng": "BS - Elec Eng",
    "BSME - Mech Eng": "BS - Mech Eng",
    "BSN - Nursing": "BS - Nursing",
    "BSc - Applied Agr": "BS - Applied Agr",
    "BSc - Bio-Statistics": "BS - Biology",
    "BSc - Biology": "BS - Biology",
    "BSc - Chemistry": "BA - 2ndEd/Chemistry",
    "BSc - Commun Health": "BS - Public Health",
    "BSc - Computer Sci": "BS - Computer Sci",
    "BSc - Economics": "BS - Economics",
    "BSc - Env Sci": "BS - Env Sci",
    "BSc - Environmental": "BS - Env Sci",
    "BSc - Epidemiology": "BS - Public Health",
    "BSc - General Agr": "BS - Agri",
    "BSc - Mathematics": "BA - 2ndEd/Math",
    "BSc - Midwifery": "BS - Midwifery",
    "BSc - Psychology": "BA - Psychology",
    "BSc - Public Health": "BS - Public Health",
    "BSc- Agronomy": "BS - Agro",
    "BUS": "BBA - Management",
    "BUSA": "BBA - Management",
    "Banking and Finance 1": "BBA - Banking & Finance",
    "Biology 1": "BS - Biology",  # confusion around Biology 1, EDU CAS ?
    "Biology": "BS - Biology",
    "Business Administration 1": "BBA - Management",
    "CENG": "BS - Civil Eng",
    "CSENG": "BS - Computer Sci",
    "Certified MidWives 1": "BS - Midwifery",
    "Certified MidWives": "BS - Midwifery",
    "Certified MidWivesrn": "BS - Midwifery",
    "Chemistry 1": "BA - 2ndEd/Chemistry",
    "Civil Engineering 1": "BS - Civil Eng",
    "Computer Networks and Security Engineering 1": "BS - Computer Sci",  # in the curriculum we have 2 but in practice just one BS in Computer Sci
    "Computer Science 1": "BS - Computer Sci",
    "ECD": "BA - Early Child Dev",
    "ECON": "BS - Economics",
    "EEDU": "COBA - GEN",
    "EENG": "BS - Elec Eng",
    "ENVS": "BS - Env Sci",
    "EVS": "BS - Env Sci",
    "Early Childhood Education and Development 1": "BA - Early Child Dev",  # from UM_Registrations
    "Early Childhood Education and Development 2": "BA - Primary Ed",
    "Early Childhood Education and Development 3": "BA - 2ndEd/Biology",
    "Early Childhood Education and Development 4": "BA - 2ndEd/Chemistry",
    "Early Childhood Education and Development 5": "BA - 2ndEd/Eng Lit",
    "Early Childhood Education and Development 6": "BA - 2ndEd/History",
    "Early Childhood Education and Development 7": "BA - 2ndEd/Math",  # by elimination
    "Early Childhood Education and Development 8": "BA - Guidance Counseling",  # by elimination
    "Electrical Engineering 1": "BS - Elec Eng",
    "English 1": "BA - 2ndEd/Eng Lit",
    "Environmental Science 1": "BS - Env Sci",
    "Environmental Science": "BS - Env Sci",
    "French 1": "WVSTU - GEN",
    "Genera Agriculture": "BS - Agri",
    "General Agriculture": "BS - Agri",
    "General Education 1": "WVSTU - GEN",
    "ME": "BS - Mech Eng",
    "MENG": "BS - Mech Eng",
    "MID": "BS - Midwifery",
    "MIDWifery": "BS - Midwifery",
    "Machanical": "BS - Mech Eng",
    "Mathematics 1": "BA - 2ndEd/Math",
    "Mechanical Engineering 1": "BS - Mech Eng",
    "Mechanical Engineering": "BS - Mech Eng",
    "NUR": "BS - Nursing",
    "Nurse": "BS - Nursing",
    "Nursing 1": "BS - Nursing",
    "Nursing 2": "BS - Nursing",
    "Nursing": "BS - Nursing",
    "PADM": "BPA - Management",
    "PH": "BS - Public Health",
    "PSY": "BA - Psychology",
    "Psychology 1": " WVSTU - GEN",
    "Public Administration 1": "BPA - Management",
    "Public Administration": "BPA - Management",
    "Public Health 1": "BS - Public Health",
    "REMEDIAL-ENGL": "WVSTU - GEN",
    "REMEDIAL-MATH": "WVSTU - GEN",
    "RN Post Basic 1": "BS - Nursing",
    "Renewable Energy Engineering 1": "WVSTU - GEN",
    "Soccer Coaching 1": "WVSTU - GEN",
    "Undecided": "WVSTU - GEN",
    "computer science": "BS - Computer Sci",
}


COLLEGE_CURRICULUM = {
    "cohs": ["BS - Nursing", "BS - Public Health", "BS - Midwifery", "COHS - GEN"],
    "coas": ["BA - Psychology", "BS - Biology", "BS - Env Sci", "COAS - GEN"],
    "cafs": ["BS - Agro", "BS - Agri", "BS - Applied Agr", "CAFS - GEN"],
    "coet": [
        "BS - Civil Eng",
        "BS - Elec Eng",
        "BS - Mech Eng",
        "BS - Computer Sci",
        "COET - GEN",
    ],
    "coed": [
        "BA - 2ndEd/Biology",
        "BA - 2ndEd/Chemistry",
        "BA - 2ndEd/Eng Lit",
        "BA - 2ndEd/History",
        "BA - 2ndEd/Math",
        "BA - Early Child Dev",
        "BA - Guidance Counseling",
        "BA - Primary Ed",
        "COED - GEN",
    ],
    "coba": [
        "BBA - Accounting",
        "BBA - Banking & Finance",
        "BBA - Management",
        "BPA - Management",
        "BS - Economics",
        "COBA - GEN",
    ],
    "deft": ["WVSTU - GEN"],
}
