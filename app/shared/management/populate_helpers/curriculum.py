from datetime import date

from app.academics.models import Course, Curriculum, Prerequisite
from app.shared.constants import TEST_ENVIRONMENTAL_STUDIES_CURRICULUM
from app.shared.enums import SEMESTER_NUMBER, TERM_NUMBER
from app.shared.utils import expand_course_code
from app.timetable.models import AcademicYear, Semester, Term
from .utils import log


# --------------------------------- academic years ---------------------------------
def populate_academic_years(cmd, start=2009, end=None):
    """
    Build AcademicYear ► Semester ► Term scaffolding from `start`-`end`
    (end year inclusive).  The calendar we apply is:

    ┌───────────────┬────────────────┬───────────────────┐
    │ Semester #    │ Span           │ Terms (1 / 2)     │
    ├───────────────┼────────────────┼───────────────────┤
    │ 1 (First)     │ Aug-11 → Dec-20│ Sep-01→Oct-20 /   │
    │               │                │ Oct-21→Dec-20     │
    │ 2 (Second)    │ Jan-01 → Jun-01│ Jan-01→Mar-25 /   │
    │               │                │ Mar-26→Jun-01     │
    │ 3 (Vacation)  │ Jun-02 → Aug-10│ (no internal terms)│
    └───────────────┴────────────────┴───────────────────┘
    """
    end = end or date.today().year
    for y in range(start, end + 1):
        ay, _ = AcademicYear.objects.get_or_create(
            start_date=date(y, 8, 11),
            end_date=date(y + 1, 8, 10),
        )

        # ── Semester 1 ─────────────────────────────────
        sem1, _ = Semester.objects.get_or_create(
            academic_year=ay,
            number=SEMESTER_NUMBER.FIRST,
            start_date=date(y, 8, 11),
            end_date=date(y, 12, 20),
        )
        Term.objects.get_or_create(
            semester=sem1,
            number=TERM_NUMBER.FIRST,
            start_date=date(y, 9, 1),
            end_date=date(y, 10, 20),
        )
        Term.objects.get_or_create(
            semester=sem1,
            number=TERM_NUMBER.SECOND,
            start_date=date(y, 10, 21),
            end_date=date(y, 12, 20),
        )

        # ── Semester 2 ─────────────────────────────────
        sem2, _ = Semester.objects.get_or_create(
            academic_year=ay,
            number=SEMESTER_NUMBER.SECOND,
            start_date=date(y + 1, 1, 1),
            end_date=date(y + 1, 6, 1),
        )
        Term.objects.get_or_create(
            semester=sem2,
            number=TERM_NUMBER.FIRST,
            start_date=date(y + 1, 1, 1),
            end_date=date(y + 1, 3, 25),
        )
        Term.objects.get_or_create(
            semester=sem2,
            number=TERM_NUMBER.SECOND,
            start_date=date(y + 1, 3, 26),
            end_date=date(y + 1, 6, 1),
        )

        # ── Semester 3 (vacation/remedial) ─────────────
        Semester.objects.get_or_create(
            academic_year=ay,
            number=SEMESTER_NUMBER.VACATION,
            start_date=date(y + 1, 6, 2),
            end_date=date(y + 1, 8, 10),
        )

    log(cmd, f"✔ Academic years {start}–{end} populated.", "SUCCESS")


# --------------------------------- curriculum ------------------------------------
def populate_environmental_studies_curriculum(cmd, colleges):
    log(cmd, "⚙  Populating BSc Environmental Studies curriculum")

    ay, _ = AcademicYear.objects.get_or_create(
        start_date=date.today().replace(month=9, day=1)
    )

    curriculum, created = Curriculum.objects.get_or_create(
        title="BSc Environmental Studies",
        college=colleges["COAS"],
        creation_date=date.today(),
    )
    log(cmd, f"  ↳ Curriculum {curriculum.title} {'created' if created else 'found'}")

    # ---------- 1. create / cache every course that appears anywhere ----------
    course_map = {}

    # first pass – courses in the main list
    for _, col_code, code, title, credits, _ in TEST_ENVIRONMENTAL_STUDIES_CURRICULUM:
        dept_code, course_num = expand_course_code(code)
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
