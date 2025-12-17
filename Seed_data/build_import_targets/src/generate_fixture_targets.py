#!/usr/bin/env python3
"""Materialize the CSV/TSV datasets enumerated in fixtures_manifest.yaml.

This loads SmartSchool exports (scdb.xls + companion CSVs) and reuses the
build_targets helpers to emit all required files under Parsed/.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
import sys

SCRIPTS_DIR = REPO_ROOT / "Scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.append(str(SCRIPTS_DIR))

from build_targets.academics import build_courses_table, build_curricula_table, build_curriculum_courses_table, build_departments_table  # type: ignore
from build_targets.people import build_directory_faculty, build_students_table  # type: ignore
from build_targets.spaces import build_rooms_table  # type: ignore
from build_targets.timetable import build_sections_table, build_semesters_table, build_sessions_table  # type: ignore
from build_targets.registry_finance import build_registry_finance_table  # type: ignore
from build_targets.generate_academics_tables import compute_dept_college_lookup, normalize_college, normalize_course_code  # type: ignore


SMARTSCHOOL_DIR = REPO_ROOT / "Sources/SmartSchool/SmartSchool/DB250711_cleaned"
OUTPUT_DIR = REPO_ROOT / "Parsed"


def load_utf16_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep="\t", encoding="utf-16-le", low_memory=False)


def build_curriculum_college_lookup(
    curriculum_courses_df: pd.DataFrame, dept_lookup: Dict[str, str]
) -> Dict[str, str]:
    df = curriculum_courses_df.copy()
    df["Curriculum"] = df["Curriculum"].astype(str).str.strip()
    df["course_dept"] = df["CourseCode"].apply(normalize_course_code)
    df["college_code"] = df["course_dept"].map(dept_lookup)
    df = df.dropna(subset=["Curriculum"])
    grouped = (
        df.dropna(subset=["college_code"])
        .groupby("Curriculum")["college_code"]
        .agg(
            lambda series: (
                series.mode().iat[0] if not series.mode().empty else series.iloc[0]
            )
        )
    )
    return grouped.to_dict()


def build_section_curriculum_lookup(
    curriculum_courses_df: pd.DataFrame,
) -> Dict[tuple, str]:
    df = curriculum_courses_df.copy()
    df["course_dept"] = df["CourseCode"].apply(normalize_course_code)
    df["course_no"] = df["CourseNo"].astype(str).str.strip()
    df["Curriculum"] = df["Curriculum"].astype(str).str.strip()
    grouped = (
        df.dropna(subset=["course_dept", "course_no", "Curriculum"])
        .loc[lambda d: d["Curriculum"].ne("")]
        .groupby(["course_dept", "course_no"])["Curriculum"]
        .agg(lambda vals: sorted(set(vals))[0])
    )
    return grouped.to_dict()


def build_faculty_college_lookup(
    sections_df: pd.DataFrame, dept_lookup: Dict[str, str]
) -> Dict[str, str]:
    sections = sections_df.copy()
    sections["course_dept"] = sections["CourseCode"].apply(normalize_course_code)
    sections["college_code"] = sections["course_dept"].map(dept_lookup)
    sections["Instructor"] = sections["Instructor"].astype(str).str.strip()
    grouped = (
        sections.dropna(subset=["college_code"])
        .groupby("Instructor")["college_code"]
        .agg(lambda vals: vals.mode().iat[0] if not vals.mode().empty else vals.iloc[0])
    )
    return grouped.to_dict()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--smartschool-root",
        type=Path,
        default=SMARTSCHOOL_DIR,
        help="Directory containing scdb.xls + CSV exports.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Destination for generated datasets.",
    )
    args = parser.parse_args()

    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    workbook_path = args.smartschool_root / "scdb.xls"
    workbook = pd.ExcelFile(workbook_path)

    students_df = load_utf16_csv(args.smartschool_root / "UM_students.csv")
    roster_df = load_utf16_csv(args.smartschool_root / "studentcourses.csv")
    dbotransactions_df = load_utf16_csv(args.smartschool_root / "dbotransaction.csv")
    files_df = load_utf16_csv(args.smartschool_root / "files.csv")

    colleges_df = workbook.parse("UM_Colleges")
    colleges_df["CollegeCode"] = colleges_df["CollegeCode"].apply(normalize_college)
    courses_df = workbook.parse("UM_Courses")
    course_levels_df = workbook.parse("UM_CoursesLevels")
    curriculum_courses_df = workbook.parse("UM_CurriculumCourses")
    curriculums_df = workbook.parse("UM_Curriculums")
    registrations_df = workbook.parse("UM_Registrations")
    registrations_df.columns = [str(col).lower() for col in registrations_df.columns]
    staff_df = workbook.parse("UM_Staff")
    users_df = workbook.parse("Users")
    sections_df = workbook.parse("UM_CoursesSections")
    schedule_df = workbook.parse("UM_CoursesSchedule")
    periods_df = workbook.parse("UM_AcademicPeriods")

    dept_lookup = compute_dept_college_lookup(roster_df, students_df)
    curriculum_college_lookup = build_curriculum_college_lookup(
        curriculum_courses_df, dept_lookup
    )
    faculty_college_lookup = build_faculty_college_lookup(sections_df, dept_lookup)

    # Academics datasets
    academics_colleges = build_departments_table(
        courses_df=courses_df,
        course_levels_df=course_levels_df,
        colleges_df=colleges_df,
        dept_college_lookup=dept_lookup,
    )
    academics_colleges.to_csv(
        output_dir / "academics_colleges_departments.csv", index=False
    )

    academics_courses = build_courses_table(
        courses_df=courses_df,
        course_levels_df=course_levels_df,
        curriculum_courses_df=curriculum_courses_df,
    )
    academics_courses.to_csv(output_dir / "academics_courses.csv", index=False)

    academics_curricula = build_curricula_table(
        curriculums_df=curriculums_df,
        curriculum_courses_df=curriculum_courses_df,
        curriculum_college_lookup=curriculum_college_lookup,
    )
    academics_curricula.to_csv(output_dir / "academics_curricula.csv", index=False)

    curriculum_courses = build_curriculum_courses_table(
        curriculum_courses_df=curriculum_courses_df,
        course_levels_df=course_levels_df,
    )
    curriculum_courses.to_csv(
        output_dir / "academics_curriculum_courses.csv", index=False
    )

    # People
    directory_faculty = build_directory_faculty(
        staff_df=staff_df,
        users_df=users_df,
        faculty_college_lookup=faculty_college_lookup,
    )
    directory_faculty.to_csv(output_dir / "people_directory_faculty.csv", index=False)

    people_students = build_students_table(
        students_df=students_df, registrations_df=registrations_df
    )
    people_students.to_csv(output_dir / "people_students.csv", index=False)

    # Spaces
    rooms = build_rooms_table(sections_df=sections_df, schedule_df=None)
    rooms.to_csv(output_dir / "spaces_rooms.csv", index=False)

    # Timetable
    semesters = build_semesters_table(periods_df)
    sections = build_sections_table(sections_df)
    course_curriculum_lookup = build_section_curriculum_lookup(curriculum_courses_df)
    sections["curriculum_override"] = sections.apply(
        lambda row: course_curriculum_lookup.get(
            (row["course_dept"], row["course_no"]), pd.NA
        ),
        axis=1,
    )
    if "curriculum" not in sections.columns:
        sections["curriculum"] = pd.NA
    sections["curriculum"] = sections["curriculum_override"].combine_first(
        sections["curriculum"]
    )
    sections = sections.drop(columns=["curriculum_override"])
    sections = sections[
        [
            "academic_year",
            "semester_no",
            "curriculum",
            "course_dept",
            "course_no",
            "section_no",
            "faculty",
        ]
    ]
    sem_sec = sections.merge(
        semesters,
        on=["academic_year", "semester_no"],
        how="left",
        suffixes=("", "_sem"),
    )
    sem_sec = sem_sec[
        [
            "academic_year",
            "semester_no",
            "start_date",
            "end_date",
            "curriculum",
            "course_dept",
            "course_no",
            "section_no",
            "faculty",
        ]
    ].sort_values(
        ["academic_year", "semester_no", "course_dept", "course_no", "section_no"]
    )
    sem_sec.to_csv(output_dir / "timetable_semesters_sections.csv", index=False)

    sessions = build_sessions_table(schedule_df)
    sessions.to_csv(output_dir / "timetable_sessions.csv", index=False)

    # Registry + finance
    registry_finance = build_registry_finance_table(
        registrations_df=registrations_df,
        dbotransactions_df=dbotransactions_df,
        files_df=files_df,
    )
    registry_finance.to_csv(
        output_dir / "registry_finance_registrations.tsv", sep="\t", index=False
    )

    print(f"Generated datasets in {output_dir}")


if __name__ == "__main__":
    main()
