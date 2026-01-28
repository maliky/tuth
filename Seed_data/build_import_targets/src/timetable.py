"""Timetable-related transforms."""

from __future__ import annotations

from typing import Iterable, Mapping

import pandas as pd


def _normalize_ay(value: str | int | float) -> str:
    text = str(value).strip()
    if "/" in text and len(text.split("/")[0]) == 4:
        start, _, end = text.partition("/")
        return f"{start[-2:]}-{end[-2:]}"
    return text


def _build_section_id(course_code: str, course_no: str, section: str) -> str:
    return f"{course_code}{course_no}-{section}".strip("-")


def build_semesters_table(periods_df: pd.DataFrame) -> pd.DataFrame:
    """Return SemesterResource rows."""
    out = periods_df.rename(
        columns={
            "AcademicYear": "academic_year",
            "Semester": "semester_no",
            "SemesterBegins": "start_date",
            "SemesterEnds": "end_date",
        }
    )
    out["academic_year"] = out["academic_year"].apply(_normalize_ay)
    out = out[
        ["academic_year", "semester_no", "start_date", "end_date"]
    ].drop_duplicates()
    return out.sort_values(["academic_year", "semester_no"]).reset_index(drop=True)


def build_sections_table(
    sections_df: pd.DataFrame,
    curriculum_lookup: Mapping[str, str] | None = None,
) -> pd.DataFrame:
    """Return SectionResource rows."""
    sections = sections_df.rename(
        columns={
            "AcademicYear": "academic_year",
            "Semester": "semester_no",
            "CourseCode": "course_dept",
            "CourseNo": "course_no",
            "Section": "section_no",
            "Instructor": "faculty",
        }
    ).copy()
    sections["academic_year"] = sections["academic_year"].apply(_normalize_ay)
    sections["course_dept"] = sections["course_dept"].astype(str).str.strip().str.upper()
    sections["course_no"] = sections["course_no"].astype(str).str.strip()
    sections["section_no"] = sections["section_no"].astype(str).str.strip()
    sections["faculty"] = sections["faculty"].astype(str).str.strip()
    sections["section_identifier"] = sections.apply(
        lambda row: _build_section_id(
            row.course_dept,
            row.course_no,
            row.section_no,
        ),
        axis=1,
    )
    if curriculum_lookup:
        sections["curriculum"] = sections["section_identifier"].map(curriculum_lookup)
    else:
        sections["curriculum"] = pd.NA

    return sections[
        [
            "academic_year",
            "semester_no",
            "curriculum",
            "course_dept",
            "course_no",
            "section_no",
            "faculty",
        ]
    ].drop_duplicates()


def build_sessions_table(
    schedule_df: pd.DataFrame,
    *,
    extra_sessions: Iterable[pd.DataFrame] | None = None,
) -> pd.DataFrame:
    """Return SecSessionResource rows."""
    sessions = schedule_df.rename(
        columns={
            "CourseCode": "course_dept",
            "CourseNo": "course_no",
            "Section": "section_no",
            "Day": "weekday",
            "RoomNo": "room",
            "FromTime": "start_time",
            "ToTime": "end_time",
        }
    ).copy()
    sessions["course_dept"] = sessions["course_dept"].astype(str).str.strip().str.upper()
    sessions["course_no"] = sessions["course_no"].astype(str).str.strip()
    sessions["section_no"] = sessions["section_no"].astype(str).str.strip()
    sessions["section_id"] = sessions.apply(
        lambda row: _build_section_id(
            row.course_dept,
            row.course_no,
            row.section_no,
        ),
        axis=1,
    )
    sessions = sessions.assign(
        weekday=lambda df: df["weekday"].astype(str).str.strip(),
        room=lambda df: df["room"].astype(str).str.strip(),
        start_time=lambda df: df["start_time"].astype(str).str.strip(),
        end_time=lambda df: df["end_time"].astype(str).str.strip(),
    )
    sessions = sessions[
        ["section_id", "weekday", "start_time", "end_time", "room"]
    ].rename(columns={"section_id": "section_no"})

    if extra_sessions:
        extras = []
        for extra in extra_sessions:
            cols = ["section_no", "weekday", "start_time", "end_time", "room"]
            missing = [c for c in cols if c not in extra]
            if missing:
                raise KeyError(f"extra session table missing columns: {missing}")
            extras.append(extra[cols])
        if extras:
            sessions = pd.concat([sessions, *extras], ignore_index=True)

    sessions = (
        sessions.dropna(subset=["section_no", "weekday", "start_time", "end_time"])
        .drop_duplicates()
        .sort_values(["section_no", "weekday", "start_time"])
        .reset_index(drop=True)
    )
    return sessions


__all__ = [
    "build_semesters_table",
    "build_sections_table",
    "build_sessions_table",
]
