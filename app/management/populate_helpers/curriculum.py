from datetime import date
from app.models import AcademicYear, Curriculum, Course, Prerequisite
from app.constants import TEST_ENVIRONMENTAL_STUDIES_CURRICULUM
from .utils import log


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
        college=colleges["COAS"],
        academic_year=ay,
    )
    log(cmd, f"  ↳ Curriculum {curriculum.title} {'created' if created else 'found'}")

    # ---------- 1. create / cache every course that appears anywhere ----------
    course_map = {}

    # first pass – courses in the main list
    for _, _, code, title, credits, _ in TEST_ENVIRONMENTAL_STUDIES_CURRICULUM:
        dept_code, course_num = code[:3], code[3:]  # safe: 6-char rule
        course, created = Course.objects.get_or_create(
            name=dept_code,
            number=course_num,
            curriculum=curriculum,
            defaults={"title": title, "credit_hours": credits},
        )
        course_map[code] = course
        log(cmd, f"    ↳ Course {code} {'created' if created else 'found'}")

    # second pass – ensure every prerequisite course exists (create placeholder if not)
    for _, _, _, _, _, prereqs in TEST_ENVIRONMENTAL_STUDIES_CURRICULUM:
        if not prereqs:
            continue
        for prereq_code in map(str.strip, prereqs.split(";")):  # strip spaces
            if prereq_code not in course_map:
                dept_code, course_num = prereq_code[:3], prereq_code[3:]
                placeholder, _ = Course.objects.get_or_create(
                    name=dept_code,
                    number=course_num,
                    curriculum=curriculum,
                    defaults={
                        "title": f"Placeholder for {prereq_code}",
                        "credit_hours": 0,
                    },
                )
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
