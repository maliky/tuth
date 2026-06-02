#!/usr/bin/env python3
"""Build reviewable TUSIS maps from the maintained tucurricula Org sources."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable


APP_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_ROOT = Path.home() / "tucurricula"
DEFAULT_OUTPUT_DIR = APP_ROOT / "data" / "tucurricula_source_maps"
LEGACY_COURSE_FILES = (
    APP_ROOT / "Seed_data" / "Fundamentals" / "academic_course.csv",
    Path.home() / "Tusis" / "Data" / "Parsed" / "academic_course.csv",
    Path.home() / "Tusis" / "Data" / "Trimed" / "academic_course.csv",
)
LEGACY_CURRICULUM_FILES = (
    APP_ROOT / "Seed_data" / "Fundamentals" / "academic_curriculum_course.csv",
    Path.home() / "Tusis" / "Data" / "Parsed" / "academic_curriculum_course.csv",
    Path.home() / "Tusis" / "Data" / "Trimed" / "academic_curriculum_course.csv",
)

COURSE_RX = re.compile(r"^\s*([A-Z]+)\s*-?\s*(\d+[A-Z]?)", re.I)
LAB_RX = re.compile(
    r"\b(lab|laboratory|clinical|clinic|seminar|practicum|internship)\b", re.I
)
TOKEN_RX = re.compile(r"[a-z0-9]+")

LEGACY_DEPT_ALIASES = {
    "AGR": "AGRI",
    "BIO": "BIOL",
    "BUS": "BUSA",
    "CHE": "CHEM",
    "CSE": "CSEN",
    "CSENG": "CSEN",
    "ECD": "ECED",
    "EDU": "EDUC",
    "EDUP": "PEDU",
    "EED": "EEDU",
    "GLE": "GLEB",
    "NUR": "NURS",
    "PEDU": "PHED",
    "PH": "PUBH",
}


def clean(text: object) -> str:
    """Return compact display text."""
    return re.sub(r"\s+", " ", "" if text is None else str(text)).strip()


def norm_token(text: object) -> str:
    """Normalize text for key comparison."""
    return clean(text).lower()


def code_parts(code: object) -> tuple[str, str]:
    """Split a visible course code into department and number parts."""
    visible = clean(code).replace("-TODO", "").upper()
    match = COURSE_RX.match(visible)
    if not match:
        return "", ""
    return match.group(1).upper(), match.group(2).upper()


def course_key(dept: object, number: object) -> str:
    """Return a compact dept+number comparison key."""
    return re.sub(r"[^A-Z0-9]", "", f"{clean(dept)}{clean(number)}".upper())


def title_score(a: object, b: object) -> float:
    """Return a conservative similarity score for program or title labels."""
    left = norm_token(a)
    right = norm_token(b)
    if not left or not right:
        return 0.0
    seq_score = SequenceMatcher(None, left, right).ratio()
    left_tokens = set(TOKEN_RX.findall(left))
    right_tokens = set(TOKEN_RX.findall(right))
    if not left_tokens or not right_tokens:
        return seq_score
    token_score = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
    return max(seq_score, token_score)


def import_tu_audit(source_root: Path):
    """Import tucurricula's audit helper from the selected checkout."""
    audit_dir = source_root / "Audit"
    sys.path.insert(0, str(audit_dir))
    import tu_audit  # type: ignore[import-not-found]

    return tu_audit


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    """Read a CSV file if it exists, otherwise return an empty row list."""
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def first_value(row: dict[str, str], keys: Iterable[str]) -> str:
    """Return the first non-empty value from row."""
    for key in keys:
        value = clean(row.get(key))
        if value:
            return value
    return ""


def load_source_courses(source_root: Path) -> list[dict[str, str]]:
    """Extract course-description facts from tucurricula Org sources."""
    tu_audit = import_tu_audit(source_root)
    out: list[dict[str, str]] = []
    for filename in tu_audit.DEFAULT_FILES:
        df = tu_audit.extract_desc_requisites(files=[filename], root_dir=source_root)
        for rec in df.to_dict(orient="records"):
            dept, number = code_parts(rec.get("course_code"))
            raw_code = clean(rec.get("course_code"))
            visible_code = raw_code.replace("-TODO", "")
            out.append(
                {
                    "source_college": clean(rec.get("college")),
                    "source_file": filename,
                    "source_course_code": raw_code,
                    "visible_course_code": visible_code,
                    "normalized_course_key": course_key(dept, number),
                    "source_dept_code": dept,
                    "course_no": number,
                    "title": clean(rec.get("title")),
                    "credit": clean(rec.get("credit")),
                    "prerequisites": clean(rec.get("prerequisites")),
                    "corequisites": clean(rec.get("corequisites")),
                    "course_slug": clean(rec.get("course_slug")),
                    "is_todo": str(raw_code.endswith("-TODO")).lower(),
                    "lab_marker": str(
                        bool(LAB_RX.search(clean(rec.get("title"))))
                    ).lower(),
                }
            )
    return out


def load_source_programs(source_root: Path) -> list[dict[str, str]]:
    """Read the maintained college/program slug map."""
    programs_path = source_root / "Audit" / "programs.org"
    rows: list[dict[str, str]] = []
    with programs_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.startswith("|") or "---" in line or "College / Unit" in line:
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) < 3:
                continue
            college, slug, program = cells[:3]
            source_key = f"{college}:{slug}".lower().replace(" ", "-")
            rows.append(
                {
                    "source_college": college,
                    "source_slug": slug,
                    "source_curriculum_key": source_key,
                    "program_title": program,
                    "program_type": classify_program(program, slug),
                }
            )
    return rows


def classify_program(program: str, slug: str) -> str:
    """Classify a program label for downstream filtering."""
    text = f"{program} {slug}".lower()
    if "minor" in text:
        return "minor"
    if "certificate" in text:
        return "certificate"
    if "associate" in text:
        return "associate"
    if "diploma" in text:
        return "diploma"
    if "remedial" in text or "access-to-college" in text:
        return "pre-college"
    if "bachelor" in text:
        return "bachelor"
    return "other"


def load_source_program_table_counts(source_root: Path) -> Counter[str]:
    """Count source table rows by program title."""
    tu_audit = import_tu_audit(source_root)
    table_df = tu_audit.extract_program_tables(root_dir=source_root)
    counts: Counter[str] = Counter()
    for rec in table_df.to_dict(orient="records"):
        counts[clean(rec.get("program"))] += 1
    return counts


def load_legacy_courses() -> list[dict[str, str]]:
    """Load current TUSIS course seed rows as legacy comparison witnesses."""
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for path in LEGACY_COURSE_FILES:
        for row in read_csv_rows(path):
            dept = first_value(row, ("dept_code", "course_dept", "course_name"))
            number = first_value(row, ("course_no",))
            title = first_value(row, ("course_title", "title"))
            credit = first_value(row, ("credit_hours", "credit"))
            key = (dept.upper(), clean(number).upper(), title, credit)
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "legacy_source_file": str(path),
                    "legacy_dept_code": dept.upper(),
                    "course_no": clean(number).upper(),
                    "legacy_course_key": course_key(dept, number),
                    "legacy_title": title,
                    "legacy_credit": credit,
                }
            )
    return out


def load_legacy_curricula() -> list[dict[str, str]]:
    """Load current TUSIS curriculum-course rows as legacy witnesses."""
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for path in LEGACY_CURRICULUM_FILES:
        for row in read_csv_rows(path):
            dept = first_value(row, ("dept_code", "course_dept", "course_name"))
            number = first_value(row, ("course_no",))
            curriculum = first_value(row, ("curriculum", "curriculum_short_name"))
            legacy_key = course_key(dept, number)
            key = (curriculum, legacy_key)
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "legacy_source_file": str(path),
                    "legacy_curriculum": curriculum,
                    "legacy_course_key": legacy_key,
                }
            )
    return out


def build_department_map(
    source_courses: list[dict[str, str]], legacy_courses: list[dict[str, str]]
) -> list[dict[str, str]]:
    """Build reviewable legacy-to-source department candidates."""
    source_depts = {
        row["source_dept_code"] for row in source_courses if row["source_dept_code"]
    }
    legacy_depts = {
        row["legacy_dept_code"] for row in legacy_courses if row["legacy_dept_code"]
    }
    source_counts = Counter(row["source_dept_code"] for row in source_courses)
    legacy_counts = Counter(row["legacy_dept_code"] for row in legacy_courses)
    source_titles = {
        (row["source_dept_code"], row["course_no"]): row["title"]
        for row in source_courses
        if row["source_dept_code"] and row["course_no"]
    }
    legacy_titles = defaultdict(list)
    for row in legacy_courses:
        legacy_titles[(row["legacy_dept_code"], row["course_no"])].append(
            row["legacy_title"]
        )

    mapped_sources: set[str] = set()
    rows: list[dict[str, str]] = []
    for legacy in sorted(legacy_depts):
        candidates: set[str] = set()
        if legacy in source_depts:
            candidates.add(legacy)
        alias = LEGACY_DEPT_ALIASES.get(legacy)
        if alias in source_depts:
            candidates.add(alias)
        if not candidates:
            rows.append(
                dept_row(
                    legacy,
                    "",
                    legacy_counts[legacy],
                    0,
                    0,
                    0,
                    "unresolved",
                    "no source candidate",
                )
            )
            continue
        for source in sorted(candidates):
            overlap, title_matches = dept_overlap(
                legacy, source, legacy_titles, source_titles
            )
            confidence = dept_confidence(legacy, source, overlap, title_matches)
            reason = "exact_code" if legacy == source else "configured_alias"
            rows.append(
                dept_row(
                    legacy,
                    source,
                    legacy_counts[legacy],
                    source_counts[source],
                    overlap,
                    title_matches,
                    confidence,
                    reason,
                )
            )
            mapped_sources.add(source)

    for source in sorted(source_depts - mapped_sources):
        rows.append(
            dept_row(
                "",
                source,
                0,
                source_counts[source],
                0,
                0,
                "source_only",
                "not present in current Tusis seeds",
            )
        )
    return rows


def dept_overlap(
    legacy: str,
    source: str,
    legacy_titles: defaultdict[tuple[str, str], list[str]],
    source_titles: dict[tuple[str, str], str],
) -> tuple[int, int]:
    """Return course-number and title-match overlap for one dept candidate."""
    source_numbers = {
        number for dept, number in source_titles if dept == source and number
    }
    legacy_numbers = {
        number for dept, number in legacy_titles if dept == legacy and number
    }
    shared_numbers = source_numbers & legacy_numbers
    title_matches = 0
    for number in shared_numbers:
        source_title = source_titles.get((source, number), "")
        if any(
            title_score(title, source_title) >= 0.72
            for title in legacy_titles[(legacy, number)]
        ):
            title_matches += 1
    return len(shared_numbers), title_matches


def dept_confidence(legacy: str, source: str, overlap: int, title_matches: int) -> str:
    """Classify department-map confidence."""
    if legacy == source:
        return "exact"
    if title_matches:
        return "high"
    if overlap:
        return "medium"
    return "candidate"


def dept_row(
    legacy: str,
    source: str,
    legacy_count: int,
    source_count: int,
    overlap: int,
    title_matches: int,
    confidence: str,
    reason: str,
) -> dict[str, str]:
    """Create a normalized department-map row."""
    return {
        "legacy_tusis_dept": legacy,
        "source_dept_code": source,
        "legacy_course_count": str(legacy_count),
        "source_course_count": str(source_count),
        "shared_course_numbers": str(overlap),
        "title_matches": str(title_matches),
        "confidence": confidence,
        "reason": reason,
    }


def build_curriculum_map(
    source_programs: list[dict[str, str]],
    legacy_curricula: list[dict[str, str]],
    table_counts: Counter[str],
) -> list[dict[str, str]]:
    """Build current Tusis curriculum names to source program candidates."""
    legacy_counts = Counter(row["legacy_curriculum"] for row in legacy_curricula)
    used_source_keys: set[str] = set()
    rows: list[dict[str, str]] = []
    for legacy_name in sorted(name for name in legacy_counts if name):
        candidates = []
        for program in source_programs:
            score = title_score(legacy_name, program["program_title"])
            if score >= 0.42:
                candidates.append((score, program))
        candidates.sort(key=lambda item: item[0], reverse=True)
        if not candidates:
            rows.append(
                curriculum_row(
                    legacy_name, {}, legacy_counts[legacy_name], 0, 0.0, "unresolved"
                )
            )
            continue
        for score, program in candidates[:4]:
            used_source_keys.add(program["source_curriculum_key"])
            rows.append(
                curriculum_row(
                    legacy_name,
                    program,
                    legacy_counts[legacy_name],
                    table_counts[program["program_title"]],
                    score,
                    curriculum_confidence(score),
                )
            )

    for program in source_programs:
        if program["source_curriculum_key"] in used_source_keys:
            continue
        rows.append(
            curriculum_row(
                "", program, 0, table_counts[program["program_title"]], 0.0, "source_only"
            )
        )
    return rows


def curriculum_confidence(score: float) -> str:
    """Classify curriculum-map confidence from a text score."""
    if score >= 0.82:
        return "high"
    if score >= 0.62:
        return "medium"
    return "candidate"


def curriculum_row(
    legacy_name: str,
    program: dict[str, str],
    legacy_count: int,
    source_count: int,
    score: float,
    confidence: str,
) -> dict[str, str]:
    """Create a normalized curriculum-map row."""
    return {
        "legacy_tusis_curriculum": legacy_name,
        "source_college": program.get("source_college", ""),
        "source_slug": program.get("source_slug", ""),
        "source_curriculum_key": program.get("source_curriculum_key", ""),
        "source_program": program.get("program_title", ""),
        "program_type": program.get("program_type", ""),
        "legacy_course_count": str(legacy_count),
        "source_table_course_count": str(source_count),
        "match_score": f"{score:.3f}",
        "confidence": confidence,
    }


def write_tsv(path: Path, rows: list[dict[str, str]]) -> None:
    """Write rows to TSV, preserving field order from the first row."""
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def write_summary(path: Path, facts: dict[str, int | str]) -> None:
    """Write a small plain-text summary for quick inspection."""
    with path.open("w", encoding="utf-8") as handle:
        for key, value in facts.items():
            handle.write(f"{key}: {value}\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_root = args.source_root.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    source_courses = load_source_courses(source_root)
    source_programs = load_source_programs(source_root)
    source_table_counts = load_source_program_table_counts(source_root)
    legacy_courses = load_legacy_courses()
    legacy_curricula = load_legacy_curricula()
    department_map = build_department_map(source_courses, legacy_courses)
    curriculum_map = build_curriculum_map(
        source_programs, legacy_curricula, source_table_counts
    )

    write_tsv(output_dir / "source_course_catalog.tsv", source_courses)
    write_tsv(output_dir / "source_program_map.tsv", source_programs)
    write_tsv(output_dir / "department_code_map.tsv", department_map)
    write_tsv(output_dir / "curriculum_code_map.tsv", curriculum_map)
    write_summary(
        output_dir / "SUMMARY.txt",
        {
            "source_root": str(source_root),
            "source_course_rows": len(source_courses),
            "source_program_rows": len(source_programs),
            "legacy_course_rows": len(legacy_courses),
            "legacy_curriculum_rows": len(legacy_curricula),
            "department_map_rows": len(department_map),
            "curriculum_map_rows": len(curriculum_map),
        },
    )
    print(f"wrote tucurricula source maps to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
