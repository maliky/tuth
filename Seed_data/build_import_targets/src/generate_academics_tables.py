#!/usr/bin/env python3
"""Generate academics CSV targets from SmartSchool exports.

This helper loads the SmartSchool workbook + companion CSV files,
derives the college/department lookup, and materializes:
  - Parsed/academics_colleges_departments.csv
  - Parsed/academics_courses.csv

It reuses the transformation helpers in Scripts/build_targets/academics.py
so the outputs mirror what the Django importers expect (see
Tests/fixtures_manifest.yaml).
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import pandas as pd

# Ensure we can import Scripts.build_targets.*
REPO_ROOT = Path(__file__).resolve().parents[2]
import sys

if str(REPO_ROOT / "Scripts") not in sys.path:
    sys.path.append(str(REPO_ROOT / "Scripts"))

from build_targets.academics import (  # type: ignore
    build_courses_table,
    build_departments_table,
)

SMARTSCHOOL_DIR = REPO_ROOT / "Sources/SmartSchool/SmartSchool/DB250711_cleaned"
DEFAULT_WORKBOOK = SMARTSCHOOL_DIR / "scdb.xls"
DEFAULT_STUDENTS = SMARTSCHOOL_DIR / "UM_students.csv"
DEFAULT_ROSTER = SMARTSCHOOL_DIR / "studentcourses.csv"
OUTPUT_DIR = REPO_ROOT / "Parsed"

COLLEGE_RENAMES = {
    "CBA": "COBA",
    "COBA": "COBA",
    "CAS": "COAS",
    "COAS": "COAS",
    "CET": "COET",
    "COET": "COET",
    "CHS": "COHS",
    "COHS": "COHS",
    "CED": "COED",
    "COED": "COED",
    "CAFS": "CAFS",
    "EDRCE": "COED",  # map to renamed code
}


def normalize_student_id(value: object) -> str | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    text = str(value).strip().upper()
    text = text.replace("TU-", "").replace("TU", "")
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return None
    return str(int(digits))


def normalize_course_code(value: object) -> str | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    token = str(value).strip().upper()
    return token or None


def normalize_college(value: object) -> str | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    token = str(value).strip().upper()
    if not token:
        return None
    return COLLEGE_RENAMES.get(token, token)


def compute_dept_college_lookup(
    roster: pd.DataFrame, students: pd.DataFrame
) -> dict[str, str]:
    """Map course departments to colleges using roster enrollments."""
    students = students.copy()
    students["_student_id"] = students["StudentID"].apply(normalize_student_id)
    students["_college"] = students["College"].apply(normalize_college)

    roster = roster.copy()
    roster["_student_id"] = roster["StudentID"].apply(normalize_student_id)
    roster["_course_code"] = roster["CourseCode"].apply(normalize_course_code)

    merged = roster.merge(
        students[["_student_id", "_college"]],
        on="_student_id",
        how="left",
    )
    merged = merged.dropna(subset=["_course_code", "_college"])

    if merged.empty:
        return {}

    lookup = (
        merged.groupby("_course_code")["_college"]
        .agg(lambda s: s.mode().iat[0] if not s.mode().empty else None)
        .dropna()
        .to_dict()
    )
    return lookup


def build_tables(workbook: Path, students_csv: Path, roster_csv: Path) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    xls = pd.ExcelFile(workbook)
    colleges_df = xls.parse("UM_Colleges")
    colleges_df["CollegeCode"] = colleges_df["CollegeCode"].apply(normalize_college)

    courses_df = xls.parse("UM_Courses")
    course_levels_df = xls.parse("UM_CoursesLevels")
    curriculum_courses_df = xls.parse("UM_CurriculumCourses")

    students_df = pd.read_csv(
        students_csv, sep="\t", encoding="utf-16-le", low_memory=False
    )
    roster_df = pd.read_csv(roster_csv, sep="\t", encoding="utf-16-le", low_memory=False)

    dept_lookup = compute_dept_college_lookup(roster_df, students_df)

    departments = build_departments_table(
        courses_df=courses_df,
        course_levels_df=course_levels_df,
        colleges_df=colleges_df,
        dept_college_lookup=dept_lookup,
    )
    departments.to_csv(OUTPUT_DIR / "academics_colleges_departments.csv", index=False)

    courses = build_courses_table(
        courses_df=courses_df,
        course_levels_df=course_levels_df,
        curriculum_courses_df=curriculum_courses_df,
    )
    courses.to_csv(OUTPUT_DIR / "academics_courses.csv", index=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workbook",
        type=Path,
        default=DEFAULT_WORKBOOK,
        help="Path to SmartSchool scdb.xls workbook.",
    )
    parser.add_argument(
        "--students-csv",
        type=Path,
        default=DEFAULT_STUDENTS,
        help="Path to UM_students.csv export.",
    )
    parser.add_argument(
        "--roster-csv",
        type=Path,
        default=DEFAULT_ROSTER,
        help="Path to studentcourses.csv export.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_tables(args.workbook, args.students_csv, args.roster_csv)
    print(
        f"Wrote academics_colleges_departments.csv and academics_courses.csv to {OUTPUT_DIR}"
    )


if __name__ == "__main__":
    main()
