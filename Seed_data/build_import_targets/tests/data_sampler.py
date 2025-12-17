#!/usr/bin/env python3
"""Trim SmartSchool datasets down to a COBA-only sample for local testing.

The sampler reads the SmartSchool exports (CSV + scdb.xls), selects a
deterministic subset of students in the requested college, and filters every
related table so referential integrity is preserved.  The resulting files are
written under ``Sources/Trimed/<college>/SmartSchool`` together with a JSON
manifest that lists the keys included in the sample.

Example:
    python Scripts/tests/data_sampler.py --student-count 320
"""

from __future__ import annotations

import argparse
import json
import math
import random
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import pandas as pd

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML ships with the project
    yaml = None

pd.options.mode.copy_on_write = True

# Old SmartSchool college codes that were renamed in the Tusis data model.
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
}


def normalize_student_id(value: object) -> str | None:
    """Return a comparable StudentID (digits only) or None."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.upper().replace("TU-", "").replace("TU", "").strip()
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return None
    return str(int(digits))


def normalize_college_code(value: object) -> str | None:
    """Map SmartSchool college tokens to the canonical Tusis codes."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    code = str(value).strip().upper()
    if not code:
        return None
    return COLLEGE_RENAMES.get(code, code)


def normalize_token(value: object) -> str | None:
    """Return a stripped string without the trailing '.0' Excel artifacts."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    token = str(value).strip()
    if token.endswith(".0"):
        token = token[:-2]
    return token or None


def normalize_course_code(value: object) -> str | None:
    token = normalize_token(value)
    return token.upper() if token else None


def ensure_clean_dir(path: Path, *, overwrite: bool) -> None:

    # > add docs. could go to a file utils package
    if path.exists():
        if not overwrite and any(path.iterdir()):
            raise SystemExit(
                f"{path} already exists and is not empty. Pass --overwrite to reuse it."
            )
    path.mkdir(parents=True, exist_ok=True)


def reset_directory(path: Path) -> None:
    # > add docs. could go to a file utils package
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        return
    for child in path.iterdir():
        if child.is_file() or child.is_symlink():
            child.unlink()
        else:
            shutil.rmtree(child)


@dataclass
class SamplerConfig:
    smartschool_root: Path
    manifest_path: Path | None
    output_dir: Path
    college_code: str = "COBA"
    student_count: int = 320
    seed: int = 20241121
    overwrite: bool = False

    @property
    def scdb_path(self) -> Path:
        return self.smartschool_root / "scdb.xls"

    @property
    def smartschool_out_dir(self) -> Path:
        return self.output_dir / "SmartSchool"

    @property
    def manual_out_dir(self) -> Path:
        return self.output_dir / "ManualSources"


class SmartSchoolWorkbook:
    """Lazy loader for scdb.xls sheets (keeps everything in-memory)."""

    def __init__(self, workbook_path: Path):
        self.workbook_path = workbook_path
        self._excel_file: pd.ExcelFile | None = None
        self._cache: dict[str, pd.DataFrame] = {}

    def load(self, sheet_name: str) -> pd.DataFrame:
        if sheet_name not in self._cache:
            if self._excel_file is None:
                if not self.workbook_path.exists():
                    raise FileNotFoundError(self.workbook_path)
                self._excel_file = pd.ExcelFile(self.workbook_path)
            self._cache[sheet_name] = self._excel_file.parse(sheet_name=sheet_name)
        return self._cache[sheet_name].copy()


@dataclass
class SampleKeys:
    # ? Explain why pyright field here ?
    student_ids: set[str] = field(default_factory=set)
    curricula: set[str] = field(default_factory=set)
    course_codes: set[str] = field(default_factory=set)
    section_keys: set[tuple[str, str, str, str, str]] = field(default_factory=set)
    session_keys: set[tuple[str, str, str]] = field(default_factory=set)
    term_keys: set[tuple[str, str]] = field(default_factory=set)
    instructor_names: set[str] = field(default_factory=set)
    invoice_refs: set[str] = field(default_factory=set)


class SmartSchoolSampler:
    def __init__(self, config: SamplerConfig):
        self.config = config
        self.workbook = SmartSchoolWorkbook(config.scdb_path)
        ensure_clean_dir(config.output_dir, overwrite=config.overwrite)
        reset_directory(config.smartschool_out_dir)
        reset_directory(config.manual_out_dir)
        self.summary: dict[str, int] = {}
        self._passthrough_sources = self._load_passthrough_sources()

    # ------------------------------------------------------------------ #
    # Loading helpers
    # ------------------------------------------------------------------ #
    def load_students(self) -> pd.DataFrame:
        path = self.config.smartschool_root / "UM_students.csv"
        return pd.read_csv(path, sep="\t", encoding="utf-16-le", low_memory=False)

    def load_student_courses(self) -> pd.DataFrame:
        path = self.config.smartschool_root / "studentcourses.csv"
        return pd.read_csv(path, sep="\t", encoding="utf-16-le", low_memory=False)

    def load_registrations(self) -> pd.DataFrame:
        return self.workbook.load("UM_Registrations")

    def load_staff(self) -> pd.DataFrame:
        return self.workbook.load("UM_Staff")

    def load_users(self) -> pd.DataFrame:
        return self.workbook.load("Users")

    def load_files(self) -> pd.DataFrame:
        path = self.config.smartschool_root / "files.csv"
        return pd.read_csv(path, sep="\t", encoding="utf-16-le", low_memory=False)

    def load_transactions(self) -> pd.DataFrame:
        path = self.config.smartschool_root / "dbotransaction.csv"
        return pd.read_csv(path, sep="\t", encoding="utf-16-le", low_memory=False)

    # ------------------------------------------------------------------ #
    # Sampling + filtering
    # ------------------------------------------------------------------ #
    def sample_students(self, students_df: pd.DataFrame) -> pd.DataFrame:
        df = students_df.copy()
        df["_normalized_college"] = df["College"].apply(normalize_college_code)
        df["_normalized_student_id"] = df["StudentID"].apply(normalize_student_id)
        df["_level_bucket"] = (
            df["YearOfEntry"]
            .fillna(df["SemesterOfEntry"])
            .apply(normalize_token)
            .fillna("UNKNOWN")
        )

        target_df = df[df["_normalized_college"] == self.config.college_code]
        target_df = target_df[target_df["_normalized_student_id"].notna()]
        if target_df.empty:
            raise SystemExit(f"No students found for college {self.config.college_code}.")
        requested = min(self.config.student_count, len(target_df))
        sampled_idx = self._sample_indices(
            target_df, "_level_bucket", requested=requested
        )
        sampled = target_df.loc[sampled_idx].copy()
        sampled = sampled.drop(columns=["_normalized_college", "_level_bucket"])
        sampled = sampled.sort_values(by="StudentID").reset_index(drop=True)
        return sampled

    def _sample_indices(
        self, df: pd.DataFrame, bucket_col: str, *, requested: int
    ) -> list[int]:
        # > Add documentation
        rng = random.Random(self.config.seed)
        unique_buckets = [
            b for b in df[bucket_col].astype(str).fillna("UNKNOWN").unique()
        ]
        unique_buckets.sort()
        per_bucket = max(1, math.ceil(requested / len(unique_buckets)))
        selected: list[int] = []
        for bucket in unique_buckets:
            bucket_idx = df.index[df[bucket_col] == bucket].tolist()
            rng.shuffle(bucket_idx)
            selected.extend(bucket_idx[:per_bucket])
        if len(selected) < requested:
            remaining = [idx for idx in df.index if idx not in selected]
            rng.shuffle(remaining)
            selected.extend(remaining[: requested - len(selected)])
        return selected[:requested]

    def build_keys(
        self,
        students: pd.DataFrame,
        registrations: pd.DataFrame,
        roster: pd.DataFrame,
    ) -> SampleKeys:
        # > add doc. why do we need to build keys ?
        keys = SampleKeys()
        keys.student_ids = {
            normalize_student_id(value) for value in students["StudentID"]
        } - {None}
        keys.curricula = {
            normalize_token(value)
            for value in students.get("Curriculum", pd.Series(dtype=object))
        } - {None}
        program_ids = {
            normalize_token(value)
            for value in students.get("ProgramID", pd.Series(dtype=object))
        } - {None}
        keys.curricula.update(program_ids)

        roster = roster.assign(
            _course_code=roster["CourseCode"].apply(normalize_course_code),
            _course_no=roster["CourseNo"].apply(normalize_token),
            _section=roster["Section"].apply(normalize_token),
            _year=roster["AcademicYear"].apply(normalize_token),
            _semester=roster["Semester"].apply(lambda v: normalize_token(v) or "1"),
        )

        for _, row in roster.iterrows():
            course_code = row["_course_code"]
            course_no = row["_course_no"]
            section = row["_section"]
            year = row["_year"]
            semester = row["_semester"]
            if course_code:
                keys.course_codes.add(course_code)
            if course_code and course_no:
                keys.session_keys.add((course_code, course_no, section or "1"))
            if course_code and course_no and section and year:
                keys.section_keys.add(
                    (course_code, course_no, section, year, semester or "1")
                )
            if year:
                keys.term_keys.add((year, semester or "1"))

        reg_terms = registrations.assign(
            _year=registrations["AcademicYear"].apply(normalize_token),
            _semester=registrations["Semester"].apply(
                lambda v: normalize_token(v) or "1"
            ),
        )
        for _, row in reg_terms.iterrows():
            year = row["_year"]
            sem = row["_semester"]
            if year:
                keys.term_keys.add((year, sem))
            major = normalize_token(row.get("Major"))
            if major:
                keys.curricula.add(major)
        return keys

    # ------------------------------------------------------------------ #
    # Filtering functions for each group of tables
    # ------------------------------------------------------------------ #
    def filter_students(self, students: pd.DataFrame) -> pd.DataFrame:
        students = students.assign(
            _normalized_student_id=students["StudentID"].apply(normalize_student_id)
        )
        students = students[students["_normalized_student_id"].notna()]
        return students.drop(columns=["_normalized_student_id"])

    def filter_registrations(
        self, registrations: pd.DataFrame, student_ids: set[str]
    ) -> pd.DataFrame:
        df = registrations.assign(
            _normalized_student_id=registrations["StudentID"].apply(normalize_student_id),
            _year=registrations["AcademicYear"].apply(normalize_token),
            _semester=registrations["Semester"].apply(normalize_token),
        )
        df = df[df["_normalized_student_id"].isin(student_ids)]
        return df.drop(columns=["_normalized_student_id", "_year", "_semester"])

    def filter_roster(self, roster: pd.DataFrame, student_ids: set[str]) -> pd.DataFrame:
        df = roster.assign(
            _normalized_student_id=roster["StudentID"].apply(normalize_student_id),
            _course_code=roster["CourseCode"].apply(normalize_course_code),
        )
        df = df[df["_normalized_student_id"].isin(student_ids)]
        return df.drop(columns=["_normalized_student_id", "_course_code"])

    def filter_curricula_tables(self, keys: SampleKeys) -> dict[str, pd.DataFrame]:
        tables: dict[str, pd.DataFrame] = {}
        curriculums_df = self.workbook.load("UM_Curriculums")
        tables["UM_Curriculums"] = curriculums_df[
            curriculums_df["Curriculum"].apply(normalize_token).isin(keys.curricula)
        ]

        curr_courses = self.workbook.load("UM_CurriculumCourses")
        curr_courses["_curriculum"] = curr_courses["Curriculum"].apply(normalize_token)
        curr_courses["_course_code"] = curr_courses["CourseCode"].apply(
            normalize_course_code
        )
        mask = curr_courses["_curriculum"].isin(keys.curricula) | curr_courses[
            "_course_code"
        ].isin(keys.course_codes)
        filtered_curr_courses = curr_courses[mask].drop(
            columns=["_curriculum", "_course_code"]
        )
        tables["UM_CurriculumCourses"] = filtered_curr_courses
        additional_codes: set[str] = set()
        for code in filtered_curr_courses["CourseCode"].tolist():
            normalized = normalize_course_code(code)
            if normalized:
                additional_codes.add(normalized)
        keys.course_codes.update(additional_codes)

        courses = self.workbook.load("UM_Courses")
        courses["_course_code"] = courses["CourseCode"].apply(normalize_course_code)
        tables["UM_Courses"] = courses[
            courses["_course_code"].isin(keys.course_codes)
        ].drop(columns=["_course_code"])

        course_levels = self.workbook.load("UM_CoursesLevels")
        course_levels["_course_code"] = course_levels["CourseCode"].apply(
            normalize_course_code
        )
        tables["UM_CoursesLevels"] = course_levels[
            course_levels["_course_code"].isin(keys.course_codes)
        ].drop(columns=["_course_code"])

        colleges = self.workbook.load("UM_Colleges")
        desired = {
            code
            for code, mapped in COLLEGE_RENAMES.items()
            if mapped == self.config.college_code
        } | {self.config.college_code}
        colleges["_normalized"] = colleges["CollegeCode"].apply(normalize_college_code)
        tables["UM_Colleges"] = colleges[
            colleges["CollegeCode"].isin(desired)
            | colleges["_normalized"].eq(self.config.college_code)
        ].drop(columns=["_normalized"])
        return tables

    def filter_sections(self, keys: SampleKeys) -> dict[str, pd.DataFrame]:
        tables: dict[str, pd.DataFrame] = {}
        sections = self.workbook.load("UM_CoursesSections")
        sections = sections.assign(
            _course_code=sections["CourseCode"].apply(normalize_course_code),
            _course_no=sections["CourseNo"].apply(normalize_token),
            _section=sections["Section"].apply(normalize_token),
            _year=sections["AcademicYear"].apply(normalize_token),
            _semester=sections["Semester"].apply(lambda v: normalize_token(v) or "1"),
        )

        def row_to_key(row: pd.Series) -> tuple[str, str, str, str, str]:
            return (
                row["_course_code"],
                row["_course_no"],
                row["_section"],
                row["_year"],
                row["_semester"],
            )

        sections["_key"] = sections.apply(row_to_key, axis=1)
        mask = sections["_key"].isin(keys.section_keys)
        filtered_sections = sections[mask].drop(
            columns=[
                "_course_code",
                "_course_no",
                "_section",
                "_year",
                "_semester",
                "_key",
            ]
        )
        tables["UM_CoursesSections"] = filtered_sections

        schedules = self.workbook.load("UM_CoursesSchedule")
        schedules = schedules.assign(
            _course_code=schedules["CourseCode"].apply(normalize_course_code),
            _course_no=schedules["CourseNo"].apply(normalize_token),
            _section=schedules["Section"].apply(normalize_token),
        )
        schedules["_key"] = schedules.apply(
            lambda row: (row["_course_code"], row["_course_no"], row["_section"]),
            axis=1,
        )
        tables["UM_CoursesSchedule"] = schedules[
            schedules["_key"].isin(keys.session_keys)
        ].drop(columns=["_course_code", "_course_no", "_section", "_key"])

        periods = self.workbook.load("UM_AcademicPeriods").assign(
            _year=lambda df: df["AcademicYear"].apply(normalize_token),
            _semester=lambda df: df["Semester"].apply(
                lambda v: normalize_token(v) or "1"
            ),
        )
        periods["_key"] = list(zip(periods["_year"], periods["_semester"]))
        tables["UM_AcademicPeriods"] = periods[periods["_key"].isin(keys.term_keys)].drop(
            columns=["_year", "_semester", "_key"]
        )
        return tables

    def filter_staff_tables(self, keys: SampleKeys) -> dict[str, pd.DataFrame]:
        tables: dict[str, pd.DataFrame] = {}
        sections = self.workbook.load("UM_CoursesSections").assign(
            _course_code=lambda df: df["CourseCode"].apply(normalize_course_code),
            _course_no=lambda df: df["CourseNo"].apply(normalize_token),
            _section=lambda df: df["Section"].apply(normalize_token),
            _year=lambda df: df["AcademicYear"].apply(normalize_token),
            _semester=lambda df: df["Semester"].apply(
                lambda v: normalize_token(v) or "1"
            ),
        )
        sections["_key"] = list(
            zip(
                sections["_course_code"],
                sections["_course_no"],
                sections["_section"],
                sections["_year"],
                sections["_semester"],
            )
        )
        instructor_names = sections.loc[
            sections["_key"].isin(keys.section_keys), "Instructor"
        ]
        instructor_set = {
            (normalize_token(name) or "").strip() for name in instructor_names.dropna()
        }
        instructor_set.discard("")

        staff_df = self.load_staff()
        staff_df["_name"] = staff_df["Staff"].apply(lambda v: (v or "").strip())
        filtered_staff = staff_df[staff_df["_name"].isin(instructor_set)].drop(
            columns=["_name"]
        )
        tables["UM_Staff"] = filtered_staff
        tables["Users"] = self.load_users()
        keys.instructor_names = instructor_set
        return tables

    def filter_finance_tables(self, keys: SampleKeys) -> dict[str, pd.DataFrame]:
        tables: dict[str, pd.DataFrame] = {}

        files_df = self.load_files()
        files_df["_student"] = files_df["Entity"].apply(normalize_student_id)
        filtered_files = files_df[files_df["_student"].isin(keys.student_ids)]
        tables["files"] = filtered_files.drop(columns=["_student"])

        reference_map: dict[str, set[str]] = {}
        for _, row in filtered_files.iterrows():
            reference = normalize_token(row["Reference"])
            student = normalize_student_id(row["Entity"])
            if not reference:
                continue
            bucket = reference_map.setdefault(reference, set())
            if student:
                bucket.add(student)
        keys.invoice_refs = set(reference_map.keys())

        transactions = self.load_transactions()
        transactions["_student"] = transactions["Entity"].apply(normalize_student_id)
        transactions["_reference"] = transactions["Reference"].apply(normalize_token)

        mask_entity = transactions["_student"].isin(keys.student_ids)
        base = transactions[mask_entity].copy()

        ref_mask = transactions["_reference"].isin(reference_map)
        extra = transactions[~mask_entity & ref_mask].copy()
        if not extra.empty:
            allowed_pairs: set[tuple[str, str | None]] = set()
            for reference, students in reference_map.items():
                if students:
                    allowed_pairs.update({(reference, sid) for sid in students})
                allowed_pairs.add((reference, None))
            extra["_student_key"] = extra["_student"].where(
                extra["_student"].notna(), None
            )
            keep_mask = [
                (ref, sid) in allowed_pairs
                for ref, sid in zip(extra["_reference"], extra["_student_key"])
            ]
            extra = extra[keep_mask]

        filtered_tx = pd.concat([base, extra], ignore_index=True)
        filtered_tx = filtered_tx.drop(columns=["_student", "_reference"])
        tables["dbotransaction"] = filtered_tx
        return tables

    # ------------------------------------------------------------------ #
    def _load_passthrough_sources(self) -> set[str]:
        """Return the name of tables from the manifest for which we take it all."""
        if not self.config.manifest_path or not self.config.manifest_path.exists():
            return set()
        if yaml is None:
            return set()
        data = yaml.safe_load(self.config.manifest_path.read_text())
        passthrough: set[str] = set()
        for block in data or []:
            for source in block.get("sources", []):
                fields = source.get("fields")
                if isinstance(fields, list) and len(fields) == 0:
                    passthrough.add(source["name"])
        return passthrough

    def copy_manual_sources(self) -> None:
        """Copy the files found in _passthrough to the out_dir."""
        # $ I find this very abstract, and I do not yet see the utility.
        # $ Also the non functional style is troubling for me
        # $ it makes it harder to follow.

        manual_sources = {
            "people.ods": Path("Sources/people.ods"),
            "schedule_25-26s1_cleaned.xlsx": Path(
                "Sources/schedule_25-26s1_cleaned.xlsx"
            ),
            "schedule_25-26s2-draft.xlsx": Path("Sources/schedule_25-26s2-draft.xlsx"),
        }
        if self._passthrough_sources:
            candidates = {
                name: manual_sources[name]
                for name in self._passthrough_sources
                if name in manual_sources
            }
        else:
            candidates = manual_sources
        for name, source in candidates.items():
            if not source.exists():
                continue
            destination = self.config.manual_out_dir / name
            shutil.copy2(source, destination)

    def write_tables(self, tables: dict[str, pd.DataFrame]) -> None:
        for name, df in tables.items():
            out_path = self.config.smartschool_out_dir / f"{name}.csv"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(out_path, index=False)
            self.summary[name] = len(df)

    def write_manifest(self, keys: SampleKeys, students_written: int) -> None:
        manifest = {
            "college_code": self.config.college_code,
            "requested_students": self.config.student_count,
            "written_students": students_written,
            "seed": self.config.seed,
            "student_ids": sorted(keys.student_ids),
            "curricula": sorted(keys.curricula),
            "course_codes": sorted(keys.course_codes),
            "sections": sorted(keys.section_keys),
            "terms": sorted(keys.term_keys),
            "invoice_references": sorted(keys.invoice_refs),
            "tables": self.summary,
        }
        manifest_path = self.config.output_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2))

    def run(self) -> None:
        print("Loading SmartSchool exports…")
        students = self.load_students()
        sampled_students = self.sample_students(students)
        filtered_students = self.filter_students(sampled_students)

        student_ids = {
            normalize_student_id(value)
            for value in filtered_students["StudentID"].tolist()
        }
        student_ids.discard(None)

        roster = self.filter_roster(self.load_student_courses(), student_ids)
        registrations = self.filter_registrations(self.load_registrations(), student_ids)

        keys = self.build_keys(filtered_students, registrations, roster)
        keys.student_ids = student_ids

        tables: dict[str, pd.DataFrame] = {
            "UM_students": filtered_students,
            "UM_Registrations": registrations,
            "studentcourses": roster,
        }
        tables.update(self.filter_curricula_tables(keys))
        tables.update(self.filter_sections(keys))
        tables.update(self.filter_staff_tables(keys))
        tables.update(self.filter_finance_tables(keys))

        self.write_tables(tables)
        self.copy_manual_sources()
        self.write_manifest(keys, students_written=len(filtered_students))
        print(f"Wrote trimmed dataset to {self.config.output_dir}")
        for name, count in sorted(self.summary.items()):
            print(f"  {name}: {count} rows")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--smartschool-root",
        type=Path,
        default=Path("Sources/SmartSchool/SmartSchool/DB250711_cleaned"),
        help="Directory that contains scdb.xls and the SmartSchool CSV exports.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("Sources/Trimed/COBA"),
        help="Destination folder for the trimmed dataset.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("Tests/fixtures_manifest.yaml"),
        help="Fixture manifest (currently informational).",
    )
    parser.add_argument(
        "--college-code",
        default="COBA",
        help="Normalized college code to sample.",
    )
    parser.add_argument(
        "--student-count",
        type=int,
        default=320,
        help="How many students to keep in the trimmed dataset.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=20241121,
        help="Deterministic sampling seed.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow writing into an existing output directory.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    config = SamplerConfig(
        smartschool_root=args.smartschool_root,
        manifest_path=args.manifest if args.manifest.exists() else None,
        output_dir=args.output_dir,
        college_code=args.college_code.upper(),
        student_count=args.student_count,
        seed=args.seed,
        overwrite=args.overwrite,
    )
    sampler = SmartSchoolSampler(config)
    sampler.run()


if __name__ == "__main__":
    main()
