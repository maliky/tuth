"""People-domain transforms (faculty directory and student roster)."""

from __future__ import annotations

from typing import Mapping

import pandas as pd


def _normalize_name(value: str | float | None) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _mk_username(first: str, last: str, middle: str = "") -> str:
    first = _normalize_name(first).lower()
    middle = _normalize_name(middle).lower()
    last = _normalize_name(last).lower()
    if not last and not first:
        return ""
    pieces = [first[:1], middle[:1], last]
    return "".join(pieces).strip()


def build_directory_faculty(
    staff_df: pd.DataFrame,
    users_df: pd.DataFrame | None = None,
    faculty_college_lookup: Mapping[str, str] | None = None,
    email_domain: str = "tusis.local",
) -> pd.DataFrame:
    """Return DirectoryContactResource + FacultyResource rows."""
    staff = (
        staff_df.rename(columns={"Staff": "faculty"})
        .assign(faculty=lambda df: df["faculty"].astype(str).str.strip())
        .drop_duplicates()
    )

    usernames = None
    if users_df is not None:
        users = users_df.copy()
        users["full_name"] = (
            users[["FirstName", "MiddleName", "LastName"]]
            .fillna("")
            .agg(" ".join, axis=1)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )
        users["username"] = users["UserName"].astype(str).str.strip()
        usernames = users[["full_name", "username"]]

    if usernames is not None:
        staff = staff.merge(
            usernames,
            how="left",
            left_on="faculty",
            right_on="full_name",
        ).drop(columns=["full_name"])
    if "username" not in staff.columns:
        staff["username"] = pd.NA

    split_names = (
        staff["faculty"]
        .fillna("")
        .str.split(" ", expand=True, n=2)
        .reindex(columns=[0, 1, 2])
        .fillna("")
        .rename(columns={0: "first_name", 1: "middle_name", 2: "last_name"})
    )
    staff = pd.concat([staff, split_names], axis=1)

    staff["username"] = staff["username"].fillna(
        staff.apply(
            lambda row: _mk_username(row.first_name, row.last_name, row.middle_name),
            axis=1,
        )
    )
    staff["email"] = staff["username"].where(
        staff["username"].ne(""),
        other=pd.NA,
    )
    staff["email"] = staff["email"].apply(
        lambda val: f"{val}@{email_domain}" if pd.notna(val) else pd.NA
    )
    if faculty_college_lookup:
        staff["college_code"] = staff["faculty"].map(faculty_college_lookup)
    else:
        staff["college_code"] = pd.NA
    staff["title"] = "Faculty"

    return staff[["faculty", "username", "email", "college_code", "title"]]


def _term_sort_value(academic_year: str, semester: str | int | float) -> int:
    year = str(academic_year).split("/")[0]
    try:
        year_num = int(year)
    except ValueError:
        year_num = 0
    try:
        sem_num = int(float(semester))
    except ValueError:
        sem_num = 0
    return year_num * 10 + sem_num


def build_students_table(
    students_df: pd.DataFrame,
    registrations_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Return StudentResource-ready rows."""
    students = students_df.copy()
    students["student_name"] = (
        students[["FirstName", "MiddleName", "LastName"]]
        .fillna("")
        .agg(" ".join, axis=1)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )
    students = students.rename(
        columns={
            "StudentID": "student_id",
            "Major": "major",
            "SemesterOfEntry": "entry_semester",
            "DateOfBirth": "birth_date",
            "MaritalStatus": "marital_status",
            "Sex": "gender",
            "Nationality": "nationality",
        }
    )
    students["entry_semester"] = (
        students["entry_semester"]
        .combine_first(students["YearOfEntry"])
        .astype(str)
        .str.strip()
    )

    students = students[
        [
            "student_id",
            "student_name",
            "major",
            "entry_semester",
            "birth_date",
            "nationality",
            "marital_status",
            "gender",
        ]
    ]

    students["current_enrolled_sem"] = students["entry_semester"]

    if registrations_df is not None and not registrations_df.empty:
        regs = registrations_df.rename(
            columns={
                "studentid": "student_id",
                "academicyear": "academic_year",
                "semester": "semester_no",
            }
        )
        regs = regs.dropna(subset=["student_id"])
        regs["term_order"] = regs.apply(
            lambda row: _term_sort_value(row.academic_year, row.semester_no), axis=1
        )
        current_terms = (
            regs.sort_values("term_order")
            .groupby("student_id")
            .tail(1)[["student_id", "academic_year", "semester_no"]]
        )
        current_terms["current_enrolled_sem"] = (
            current_terms["academic_year"].astype(str).str.strip()
            + " S"
            + current_terms["semester_no"].astype(str).str.strip()
        )
        students = students.merge(
            current_terms[["student_id", "current_enrolled_sem"]],
            how="left",
            on="student_id",
            suffixes=("", "_from_regs"),
        )
        students["current_enrolled_sem"] = students[
            "current_enrolled_sem_from_regs"
        ].combine_first(students["current_enrolled_sem"])
        students = students.drop(columns=["current_enrolled_sem_from_regs"])

    return students[
        [
            "student_id",
            "student_name",
            "major",
            "entry_semester",
            "current_enrolled_sem",
            "birth_date",
            "nationality",
            "marital_status",
            "gender",
        ]
    ].sort_values("student_id")


__all__ = ["build_directory_faculty", "build_students_table"]
