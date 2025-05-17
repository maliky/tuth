from datetime import date
from app.models import AcademicYear, Curriculum, Course, Prerequisite
from app.constants import TEST_ENVIRONMENTAL_STUDIES_CURRICULUM
from .utils import log
import re


def extract_code(code):
    "Given a course code return the num and the code"
    assert "/" not in code
    rpat = r"(?P<code>[A-Z]+)(?P<num>[0-9]+)"
    return re.search(rpat, code).groups()


# --------------------------------- academic years ---------------------------------
def populate_academic_years(cmd, start=2009, end=None):
    end = end or date.today().year
    for y in range(start, end + 1):
        AcademicYear.objects.get_or_create(starting_date=date(y, 9, 1))
    log(cmd, f"✔ Academic years {start}–{end} populated.", "SUCCESS")


# --------------------------------- curriculum ------------------------------------
def populate_environmental_studies_curriculum(cmd, colleges):
    log(cmd, "⚙  Populating BSc Environmental Studies curriculum")

    ay, _ = AcademicYear.objects.get_or_create(
        starting_date=date.today().replace(month=9, day=1)
    )

    curriculum, created = Curriculum.objects.get_or_create(
        title="BSc Environmental Studies",
        level="bachelor",
        college=colleges["COAS"],
        academic_year=ay,
    )
    log(cmd, f"  ↳ Curriculum {curriculum.title} {'created' if created else 'found'}")

    # ---------- 1. create / cache every course that appears anywhere ----------
    course_map = {}

    # first pass – courses in the main list
    for _, col_code, code, title, credits, _ in TEST_ENVIRONMENTAL_STUDIES_CURRICULUM:
        dept_code, course_num = extract_code(code)
        course, created = Course.objects.get_or_create(
            name=dept_code,
            number=course_num,
            college=colleges[col_code],
            defaults={"title": title, "credit_hours": credits},
        )
        course.curricula.add(curriculum)
        course_map[code] = course
        log(cmd, f"    ↳ Course {code} {'created' if created else 'found'}")

    # second pass – ensure every prerequisite course exists (create placeholder if not)
    for _, col_code, _, _, _, prereqs in TEST_ENVIRONMENTAL_STUDIES_CURRICULUM:
        if not prereqs:
            continue
        for prereq_code in map(str.strip, prereqs.split(";")):  # strip spaces
            if prereq_code not in course_map:
                dept_code, course_num = prereq_code[:3], prereq_code[3:]
                placeholder, _ = Course.objects.get_or_create(
                    name=dept_code,
                    number=course_num,
                    college=colleges[col_code],
                    defaults={
                        "title": f"Placeholder for {prereq_code}",
                        "credit_hours": 0,
                    },
                )
                placeholder.curricula.add(curriculum)
                course_map[prereq_code] = placeholder
                log(cmd, f"    ↳ Placeholder course {prereq_code} created")

    # ---------- 2. create prerequisite rows (all courses now guaranteed) ----------
    for _, _, code, _, _, prereqs in TEST_ENVIRONMENTAL_STUDIES_CURRICULUM:
        if not prereqs:
            continue
        for prereq_code in map(str.strip, prereqs.split(";")):
            Prerequisite.objects.get_or_create(
                course=course_map[code],
                prerequisite_course=course_map[prereq_code],
                defaults={},  # add extra fields here if your model needs them
            )
            log(cmd, f"      ↳ {code} needs {prereq_code}")
