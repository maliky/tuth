"""Transform SmartSchool tables into import-friendly academics datasets."""

from __future__ import annotations

from typing import Iterable, Mapping

import pandas as pd

CollegeLookup = Mapping[str, str] | pd.Series | pd.DataFrame | None


def _normalize_lookup(
    lookup: CollegeLookup,
    *,
    key: str = "course_dept",
    value: str = "college_code",
) -> dict[str, str]:
    if lookup is None:
        return {}
    if isinstance(lookup, Mapping):
        return {str(k).strip(): str(v).strip() for k, v in lookup.items() if pd.notna(v)}
    if isinstance(lookup, pd.Series):
        return {
            str(idx).strip(): str(val).strip()
            for idx, val in lookup.items()
            if pd.notna(idx) and pd.notna(val)
        }
    if isinstance(lookup, pd.DataFrame):
        if key not in lookup or value not in lookup:
            raise KeyError(f"lookup dataframe must contain '{key}' and '{value}' columns")
        _df = lookup.dropna(subset=[key, value])
        return {
            str(row[key]).strip(): str(row[value]).strip() for _, row in _df.iterrows()
        }
    raise TypeError("lookup must be a mapping, Series, DataFrame, or None")


def build_colleges_table(colleges_df: pd.DataFrame) -> pd.DataFrame:
    """Return the normalized CollegeResource dataset."""
    cols = {
        "CollegeCode": "college_code",
        "Description": "college_long_name",
    }
    out = (
        colleges_df.rename(columns=cols)[list(cols.values())]
        .drop_duplicates()
        .assign(
            college_code=lambda df: df["college_code"]
            .astype(str)
            .str.strip()
            .str.upper(),
            college_long_name=lambda df: df["college_long_name"].astype(str).str.strip(),
        )
        .sort_values("college_code")
        .reset_index(drop=True)
    )
    return out


def build_departments_table(
    courses_df: pd.DataFrame,
    course_levels_df: pd.DataFrame,
    colleges_df: pd.DataFrame | None = None,
    dept_college_lookup: CollegeLookup = None,
) -> pd.DataFrame:
    """Map course departments to their parent colleges."""
    college_lookup = _normalize_lookup(dept_college_lookup, key="course_dept")
    colleges = build_colleges_table(colleges_df) if colleges_df is not None else None

    departments = (
        course_levels_df[["CourseCode"]]
        .drop_duplicates()
        .rename(columns={"CourseCode": "course_dept"})
    )
    dept_titles = (
        courses_df[["CourseCode", "Course"]]
        .drop_duplicates()
        .rename(columns={"CourseCode": "course_dept", "Course": "department_title"})
    )
    out = (
        departments.merge(dept_titles, how="left", on="course_dept")
        .assign(
            course_dept=lambda df: df["course_dept"].astype(str).str.strip().str.upper(),
            department_title=lambda df: df["department_title"]
            .fillna(df["course_dept"])
            .astype(str)
            .str.strip(),
            college_code=lambda df: df["course_dept"].map(college_lookup),
        )
        .sort_values("course_dept")
        .reset_index(drop=True)
    )
    if colleges is not None and "college_code" in out:
        out = out.merge(
            colleges[["college_code", "college_long_name"]],
            on="college_code",
            how="left",
        )
    else:
        out["college_long_name"] = pd.NA
    return out[["college_code", "college_long_name", "course_dept", "department_title"]]


def build_courses_table(
    courses_df: pd.DataFrame,
    course_levels_df: pd.DataFrame,
    curriculum_courses_df: pd.DataFrame | None = None,
    prerequisite_delimiter: str = ", ",
) -> pd.DataFrame:
    """Return the CourseResource dataset."""
    course_titles = courses_df[["CourseCode", "Course"]].drop_duplicates()
    merged = course_levels_df.merge(course_titles, how="left", on="CourseCode")
    merged = merged.assign(
        course_dept=lambda df: df["CourseCode"].astype(str).str.strip().str.upper(),
        course_no=lambda df: df["CourseNo"].astype(str).str.strip(),
        course_title=lambda df: df["Course"]
        .fillna(df["Description"])
        .astype(str)
        .str.strip(),
    )
    merged = merged[["course_dept", "course_no", "course_title"]]

    if curriculum_courses_df is not None:
        prereq = (
            curriculum_courses_df[["CourseCode", "CourseNo", "PreReqCode", "PreReqNo"]]
            .dropna(subset=["PreReqCode", "PreReqNo"])
            .assign(
                PreReqCode=lambda df: df["PreReqCode"]
                .astype(str)
                .str.strip()
                .str.upper(),
                PreReqNo=lambda df: df["PreReqNo"].astype(str).str.strip(),
                CourseCode=lambda df: df["CourseCode"]
                .astype(str)
                .str.strip()
                .str.upper(),
                CourseNo=lambda df: df["CourseNo"].astype(str).str.strip(),
            )
        )
        prereq["prereq"] = prereq["PreReqCode"] + " " + prereq["PreReqNo"]
        prereq = (
            prereq.groupby(["CourseCode", "CourseNo"])["prereq"]
            .agg(lambda vals: prerequisite_delimiter.join(sorted(set(vals))))
            .reset_index()
            .rename(columns={"CourseCode": "course_dept", "CourseNo": "course_no"})
        )
        merged = merged.merge(prereq, how="left", on=["course_dept", "course_no"])
    else:
        merged["prereq"] = pd.NA

    merged = merged.rename(columns={"prereq": "prerequisites"})
    return merged.sort_values(["course_dept", "course_no"]).reset_index(drop=True)


def build_curricula_table(
    curriculums_df: pd.DataFrame,
    curriculum_courses_df: pd.DataFrame,
    curriculum_college_lookup: CollegeLookup = None,
) -> pd.DataFrame:
    """Return CurriculumResource-ready rows."""
    lookup = _normalize_lookup(
        curriculum_college_lookup, key="curriculum", value="college_code"
    )
    curriculum_courses_df = curriculum_courses_df.copy()
    curriculum_courses_df["Curriculum"] = (
        curriculum_courses_df["Curriculum"].astype(str).str.strip()
    )
    curriculum_courses_df["course_pair"] = (
        curriculum_courses_df["CourseCode"].astype(str).str.strip().str.upper()
        + " "
        + curriculum_courses_df["CourseNo"].astype(str).str.strip()
    )
    course_lists = (
        curriculum_courses_df.groupby("Curriculum")["course_pair"]
        .agg(lambda vals: "; ".join(sorted(set(vals))))
        .reset_index()
    )
    out = (
        curriculums_df.rename(columns={"Curriculum": "curriculum"})
        .assign(
            curriculum=lambda df: df["curriculum"].astype(str).str.strip(),
            title=lambda df: df["curriculum"],
        )
        .merge(course_lists, how="left", left_on="curriculum", right_on="Curriculum")
        .drop(columns=["Curriculum"])
    )
    out["course_pair"] = out["course_pair"].fillna("")
    out["college_code"] = out["curriculum"].map(lookup)
    out = out.rename(columns={"course_pair": "list_courses"})
    return out[["curriculum", "title", "college_code", "list_courses"]].sort_values(
        "curriculum"
    )


def build_curriculum_courses_table(
    curriculum_courses_df: pd.DataFrame,
    course_levels_df: pd.DataFrame,
) -> pd.DataFrame:
    """Return CurriculumCourseResource-ready rows."""
    credits = course_levels_df[
        ["CourseCode", "CourseNo", "CreditHours"]
    ].drop_duplicates()
    out = (
        curriculum_courses_df[["Curriculum", "CourseCode", "CourseNo"]]
        .drop_duplicates()
        .assign(
            curriculum=lambda df: df["Curriculum"].astype(str).str.strip(),
            course_dept=lambda df: df["CourseCode"].astype(str).str.strip().str.upper(),
            course_no=lambda df: df["CourseNo"].astype(str).str.strip(),
        )
        .merge(
            credits.rename(
                columns={
                    "CourseCode": "course_dept",
                    "CourseNo": "course_no",
                    "CreditHours": "credit_hours",
                }
            ),
            how="left",
            on=["course_dept", "course_no"],
        )
    )
    return out[["curriculum", "course_dept", "course_no", "credit_hours"]].sort_values(
        ["curriculum", "course_dept", "course_no"]
    )


__all__ = [
    "build_colleges_table",
    "build_departments_table",
    "build_courses_table",
    "build_curricula_table",
    "build_curriculum_courses_table",
]
