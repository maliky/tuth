#!/usr/bin/env python3
"""Extract import-ready TUSIS TSV files from maintained TU curriculum Org files."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Iterable, TypeAlias

APP_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_ROOT))

from app.shared.course_wrangling import course_key, split_course_code  # noqa: E402

DEFAULT_SOURCE_ROOT = Path.home() / "tucurricula"
DEFAULT_OUTPUT_DIR = APP_ROOT / "data" / "tucurricula_import"
REQ_REF_RX = re.compile(
    r"(?i)(?:\\gls\{([^}]+)\}|"
    r"\b([A-Z]{3,5})\s*(\d{3}[A-Z]?)\b|"
    r"\b([a-z]{3,5})(\d{3}[a-z]?)\b)"
)
MIN_CREDIT_RX = re.compile(r"(?i)completed\s+(\d{2,3})\s+credits?")
CONCURRENT_RX = re.compile(r"(?i)concurrent|together")
OR_RX = re.compile(r"(?i)\bor\b")
RowT: TypeAlias = dict[str, str]
CourseKeyT: TypeAlias = str
SummaryValueT: TypeAlias = str | int | Path

COLLEGE_CODE_MAP = {
    "cafs": "CAFS",
    "cas": "COAS",
    "cba": "COBA",
    "ced": "COED",
    "cet": "COET",
    "chs": "COHS",
    "program centers": "DEFT",
}
REQ_KIND_ORDER = {"prereq_all": 1, "prereq_any": 2, "coreq_all": 3}


@dataclass(frozen=True)
class CourseDescT:
    """Course-description fact extracted from a ``TUCCrsDescDef`` macro."""

    source_file: str
    source_college: str
    slug: str
    code: str
    title: str
    credit: str
    description: str
    prerequisites: str
    corequisites: str


@dataclass(frozen=True)
class ProgramT:
    """Program slug/name pair from ``Audit/programs.org``."""

    source_college: str
    slug: str
    title: str


@dataclass(frozen=True)
class ReqRefT:
    """Parsed prerequisite/corequisite reference for one target course."""

    target_key: CourseKeyT
    raw_target_code: str
    raw_text: str
    ref_key: CourseKeyT
    kind: str
    source_file: str
    member_order: int


def clean(text: object) -> str:
    """Return compact display text."""
    return re.sub(r"\s+", " ", "" if text is None else str(text)).strip()


def plain_text(text: object) -> str:
    """Return a readable text value with common Org/LaTeX wrappers removed."""
    value = "" if text is None else str(text)
    value = re.sub(r"\\gls\{([^}]*)\}", r"\1", value)
    value = value.replace("\\\\", " ")
    value = value.replace(r"\/", "/")
    value = re.sub(r"\\[a-zA-Z]+", "", value)
    value = value.replace("{", "").replace("}", "")
    return clean(value)


def parse_credit(text: object) -> str:
    """Return the first integer credit value, or an empty value for audit."""
    match = re.search(r"\d+", str(text or ""))
    return match.group(0) if match else ""


def source_college_code(source_college: str) -> str:
    """Map source college labels to existing TUSIS college codes."""
    return COLLEGE_CODE_MAP.get(source_college.lower(), "DEFT")


def code_parts(code: object) -> tuple[str, str]:
    """Split a visible course code into department and number."""
    return split_course_code(clean(code))


def course_key_from_code(code: object) -> CourseKeyT:
    """Return the normalized course key for comparison and joins."""
    dept, number = code_parts(code)
    return course_key(dept, number)


def short_curriculum(source_college: str, slug: str) -> str:
    """Return the stable TUSIS curriculum short name for a source program."""
    college = "centers" if source_college.lower() == "program centers" else source_college
    return f"{college}-{slug}".upper().replace(" ", "-")[:40]


def parse_bracket(text: str, index: int) -> tuple[str, int] | None:
    """Parse one optional bracket argument from *index*."""
    if index >= len(text) or text[index] != "[":
        return None
    depth = 0
    start = index + 1
    index += 1
    while index < len(text):
        char = text[index]
        if char == "[":
            depth += 1
        elif char == "]":
            if depth == 0:
                return text[start:index], index + 1
            depth -= 1
        index += 1
    return None


def parse_braces(text: str, index: int) -> tuple[str, int] | None:
    """Parse one required braced argument from *index*, preserving nested content."""
    while index < len(text) and text[index].isspace():
        index += 1
    if index >= len(text) or text[index] != "{":
        return None
    depth = 0
    start = index + 1
    index += 1
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            if depth == 0:
                return text[start:index], index + 1
            depth -= 1
        index += 1
    return None


def iter_desc_macros(path: Path, source_college: str) -> Iterable[CourseDescT]:
    """Yield course-description facts from all ``TUCCrsDescDef`` macros in *path*."""
    text = path.read_text(encoding="utf-8")
    command = r"\TUCCrsDescDef"
    index = 0
    while True:
        found = text.find(command, index)
        if found == -1:
            return
        cursor = found + len(command)
        opts: list[str] = []
        for _ in range(2):
            while cursor < len(text) and text[cursor].isspace():
                cursor += 1
            parsed_opt = parse_bracket(text, cursor)
            if parsed_opt is None:
                break
            value, cursor = parsed_opt
            opts.append(value)
        args: list[str] = []
        for _ in range(5):
            parsed_arg = parse_braces(text, cursor)
            if parsed_arg is None:
                break
            value, cursor = parsed_arg
            args.append(value)
        if len(args) == 5:
            prereq = opts[0] if opts else ""
            coreq = opts[1] if len(opts) > 1 else ""
            slug, code, title, credit, description = args
            yield CourseDescT(
                path.name,
                source_college,
                clean(slug),
                clean(code),
                plain_text(title),
                parse_credit(credit),
                plain_text(description),
                plain_text(prereq),
                plain_text(coreq),
            )
        index = max(cursor, found + len(command))


def import_tu_audit(source_root: Path) -> ModuleType:
    """Import tucurricula's maintained audit helper."""
    audit_path = source_root / "Audit" / "tu_audit.py"
    spec = importlib.util.spec_from_file_location("tucurricula_tu_audit", audit_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import tucurricula audit helper: {audit_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_programs(source_root: Path) -> list[ProgramT]:
    """Load program labels from ``Audit/programs.org``."""
    rows: list[ProgramT] = []
    for line in (
        (source_root / "Audit" / "programs.org").read_text(encoding="utf-8").splitlines()
    ):
        if not line.startswith("|") or "---" in line or "College / Unit" in line:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 3:
            rows.append(ProgramT(cells[0], cells[1], cells[2]))
    return rows


def load_descriptions(source_root: Path) -> list[CourseDescT]:
    """Load all course-description macros from the six college source files."""
    tu_audit = import_tu_audit(source_root)
    rows: list[CourseDescT] = []
    for filename in tu_audit.DEFAULT_FILES:
        source_college = filename.split("_curriculum_")[0]
        rows.extend(iter_desc_macros(source_root / filename, source_college))
    return rows


def table_rows(source_root: Path) -> list[RowT]:
    """Return program table rows using tucurricula's maintained parser."""
    tu_audit = import_tu_audit(source_root)
    return [
        {key: clean(value) for key, value in rec.items()}
        for rec in tu_audit.extract_program_tables(root_dir=source_root).to_dict(
            orient="records"
        )
    ]


def best_title(values: Iterable[str]) -> str:
    """Return the most frequent non-empty title, preserving deterministic ties."""
    counts = Counter(clean(value) for value in values if clean(value))
    if not counts:
        return ""
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def build_course_rows(
    desc_rows: list[CourseDescT], tbl_rows: list[RowT]
) -> tuple[list[RowT], dict[CourseKeyT, RowT], list[RowT]]:
    """Build canonical course rows and conflict audit rows."""
    desc_by_key: dict[CourseKeyT, list[CourseDescT]] = defaultdict(list)
    tbl_by_key: dict[CourseKeyT, list[RowT]] = defaultdict(list)
    for desc_row in desc_rows:
        key = course_key_from_code(desc_row.code)
        if key:
            desc_by_key[key].append(desc_row)
    for tbl_row in tbl_rows:
        key = course_key_from_code(tbl_row["code"])
        if key:
            tbl_by_key[key].append(tbl_row)

    courses: list[RowT] = []
    conflicts: list[RowT] = []
    for key in sorted(set(desc_by_key) | set(tbl_by_key)):
        descs = desc_by_key.get(key, [])
        tbls = tbl_by_key.get(key, [])
        dept, number = code_parts(descs[0].code if descs else tbls[0]["code"])
        owner_college = descs[0].source_college if descs else tbls[0]["college"]
        desc_credit = next((row.credit for row in descs if row.credit), "")
        tbl_credit = next(
            (parse_credit(row["credit"]) for row in tbls if parse_credit(row["credit"])),
            "",
        )
        title = best_title([row.title for row in descs] + [row["title"] for row in tbls])
        if len({row.title for row in descs if row.title}) > 1 or (
            desc_credit and tbl_credit and desc_credit != tbl_credit
        ):
            conflicts.append(
                {
                    "course_key": key,
                    "titles": " | ".join(
                        sorted({row.title for row in descs if row.title})
                    ),
                    "description_credit": desc_credit,
                    "table_credit": tbl_credit,
                    "source_files": ";".join(sorted({row.source_file for row in descs})),
                }
            )
        courses.append(
            {
                "college_code": source_college_code(owner_college),
                "course_college_code": source_college_code(owner_college),
                "course_dept": dept,
                "course_no": number,
                "course_title": title,
                "credit_hours": desc_credit or tbl_credit or "0",
                "description": descs[0].description if descs else "",
                "source_course_key": key,
                "source_files": ";".join(sorted({row.source_file for row in descs})),
            }
        )
    by_key = {row["source_course_key"]: row for row in courses}
    return courses, by_key, conflicts


def build_curriculum_rows(
    programs: list[ProgramT],
) -> tuple[list[RowT], dict[tuple[str, str], ProgramT], dict[tuple[str, str], str]]:
    """Return import rows plus lookup maps for program table rows."""
    program_by_title = {(p.source_college.lower(), p.title): p for p in programs}
    curri_by_title = {
        (p.source_college.lower(), p.title): short_curriculum(p.source_college, p.slug)
        for p in programs
    }
    rows = [
        {
            "college_code": source_college_code(p.source_college),
            "curriculum_college_code": source_college_code(p.source_college),
            "curriculum": short_curriculum(p.source_college, p.slug),
            "long_name": p.title,
            "status": "pending",
            "source_college": p.source_college,
            "source_slug": p.slug,
        }
        for p in programs
    ]
    return rows, program_by_title, curri_by_title


def min_credit_by_course(desc_rows: list[CourseDescT]) -> dict[CourseKeyT, str]:
    """Extract safely stated minimum validated-credit gates by target course."""
    out: dict[CourseKeyT, str] = {}
    for row in desc_rows:
        text = f"{row.prerequisites} {row.corequisites}"
        match = MIN_CREDIT_RX.search(text)
        if match:
            out[course_key_from_code(row.code)] = match.group(1)
    return out


def build_curri_course_rows(
    tbl_rows: list[RowT],
    curri_by_title: dict[tuple[str, str], str],
    course_by_key: dict[CourseKeyT, RowT],
    min_credits: dict[CourseKeyT, str],
) -> tuple[list[RowT], list[RowT]]:
    """Build curriculum-course import rows and unmapped-program audit rows."""
    rows: list[RowT] = []
    unresolved: list[RowT] = []
    seen: set[tuple[str, CourseKeyT]] = set()
    for row in tbl_rows:
        lookup = (row["college"].lower(), row["program"])
        curriculum = curri_by_title.get(lookup)
        key = course_key_from_code(row["code"])
        course = course_by_key.get(key)
        if not curriculum or not course:
            unresolved.append({"reason": "missing curriculum or course", **row})
            continue
        unique = (curriculum, key)
        if unique in seen:
            continue
        seen.add(unique)
        year = int(row["year"] or 99)
        sem = int(row["semester"] or 0)
        level = ((year - 1) * 2 + sem) if 1 <= year <= 5 and sem in {1, 2} else 99
        rows.append(
            {
                "college_code": source_college_code(row["college"]),
                "curriculum_college_code": source_college_code(row["college"]),
                "course_college_code": course["course_college_code"],
                "curriculum": curriculum,
                "course_dept": course["course_dept"],
                "course_no": course["course_no"],
                "course_title": course["course_title"],
                "credit_hours": parse_credit(row["credit"]) or course["credit_hours"],
                "year_number": str(year),
                "semester_number": str(sem),
                "level_number": str(level),
                "required_group_number": "0",
                "min_validated_credits": min_credits.get(key, "0"),
                "is_required": "true",
                "source_course_key": key,
                "source_program": row["program"],
            }
        )
    return rows, unresolved


def parse_req_refs(
    row: CourseDescT, field: str, raw_text: str
) -> tuple[list[ReqRefT], list[RowT]]:
    """Parse one prerequisite/corequisite cell into resolvable raw references."""
    if not raw_text:
        return [], []
    target_key = course_key_from_code(row.code)
    kind = (
        "coreq_all"
        if field == "corequisites" or CONCURRENT_RX.search(raw_text)
        else "prereq_all"
    )
    if kind == "prereq_all" and OR_RX.search(raw_text):
        kind = "prereq_any"
    refs: list[ReqRefT] = []
    for order, match in enumerate(REQ_REF_RX.finditer(raw_text), start=1):
        if match.group(1):
            ref_key = course_key_from_code(match.group(1))
        elif match.group(2):
            ref_key = course_key_from_code(f"{match.group(2)} {match.group(3)}")
        else:
            ref_key = course_key_from_code(f"{match.group(4)} {match.group(5)}")
        if ref_key and ref_key != target_key:
            refs.append(
                ReqRefT(
                    target_key, row.code, raw_text, ref_key, kind, row.source_file, order
                )
            )
    if refs:
        return refs, []
    return [], [
        {
            "source_file": row.source_file,
            "target_course": row.code,
            "field": field,
            "raw_text": raw_text,
            "reason": "no course reference parsed",
        }
    ]


def build_requirement_rows(
    desc_rows: list[CourseDescT],
    curri_rows: list[RowT],
    course_by_key: dict[CourseKeyT, RowT],
) -> tuple[list[RowT], list[RowT]]:
    """Build grouped requirement import rows and unresolved audit rows."""
    curri_by_course: dict[CourseKeyT, list[RowT]] = defaultdict(list)
    for row in curri_rows:
        curri_by_course[row["source_course_key"]].append(row)
    rows: list[RowT] = []
    unresolved: list[RowT] = []
    for desc in desc_rows:
        parsed: list[ReqRefT] = []
        for field, raw in (
            ("prerequisites", desc.prerequisites),
            ("corequisites", desc.corequisites),
        ):
            refs, issues = parse_req_refs(desc, field, raw)
            parsed.extend(refs)
            unresolved.extend(issues)
        for ref in parsed:
            req_course = course_by_key.get(ref.ref_key)
            targets = curri_by_course.get(ref.target_key, [])
            if not req_course or not targets:
                reason_parts: list[str] = []
                if not req_course:
                    reason_parts.append("required course not mapped to import rows")
                if not targets:
                    reason_parts.append("target course not mapped to any curriculum")
                unresolved.append(
                    {
                        "source_file": ref.source_file,
                        "target_course": ref.raw_target_code,
                        "field": ref.kind,
                        "raw_text": ref.raw_text,
                        "required_course_key": ref.ref_key,
                        "reason": "; ".join(reason_parts),
                    }
                )
                continue
            for target in targets:
                rows.append(
                    {
                        "college_code": target["curriculum_college_code"],
                        "curriculum_college_code": target["curriculum_college_code"],
                        "course_college_code": target["course_college_code"],
                        "curriculum": target["curriculum"],
                        "course_dept": target["course_dept"],
                        "course_no": target["course_no"],
                        "required_course_college_code": req_course["course_college_code"],
                        "required_course_dept": req_course["course_dept"],
                        "required_course_no": req_course["course_no"],
                        "requirement_kind": ref.kind,
                        "requirement_label": f"source {ref.kind} {ref.target_key}"[:80],
                        "requirement_order": str(REQ_KIND_ORDER[ref.kind]),
                        "member_order": str(ref.member_order),
                        "source_file": ref.source_file,
                        "source_course_key": ref.target_key,
                        "raw_requisite": ref.raw_text,
                    }
                )
    return rows, unresolved


def write_tsv(path: Path, rows: list[RowT], headers: list[str] | None = None) -> None:
    """Write rows to TSV with stable headers."""
    if headers is None:
        headers = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=headers, delimiter="\t", extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)


def write_summary(path: Path, facts: dict[str, SummaryValueT]) -> None:
    """Write a compact summary file."""
    path.write_text(
        "".join(f"{key}: {value}\n" for key, value in facts.items()), encoding="utf-8"
    )


def extract(source_root: Path, output_dir: Path) -> None:
    """Extract all import and audit TSV files."""
    source_root = source_root.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    desc_rows = load_descriptions(source_root)
    tbl_rows = table_rows(source_root)
    programs = load_programs(source_root)
    curriculum_rows, _, curri_by_title = build_curriculum_rows(programs)
    course_rows, course_by_key, course_conflicts = build_course_rows(desc_rows, tbl_rows)
    curri_course_rows, unmapped_program_rows = build_curri_course_rows(
        tbl_rows, curri_by_title, course_by_key, min_credit_by_course(desc_rows)
    )
    requirement_rows, unresolved_reqs = build_requirement_rows(
        desc_rows, curri_course_rows, course_by_key
    )

    write_tsv(output_dir / "academic_curriculum.tsv", curriculum_rows)
    write_tsv(output_dir / "academic_course.tsv", course_rows)
    write_tsv(output_dir / "academic_curriculum_course.tsv", curri_course_rows)
    write_tsv(output_dir / "academic_curriculum_requirement.tsv", requirement_rows)
    write_tsv(output_dir / "course_conflicts.tsv", course_conflicts)
    write_tsv(output_dir / "description_table_mismatches.tsv", unmapped_program_rows)
    write_tsv(output_dir / "unresolved_requisites.tsv", unresolved_reqs)
    write_tsv(
        output_dir / "duplicate_course_keys.tsv",
        [
            {"source_course_key": key, "count": str(count)}
            for key, count in Counter(
                course_key_from_code(row.code) for row in desc_rows
            ).items()
            if key and count > 1
        ],
    )
    write_summary(
        output_dir / "SUMMARY.txt",
        {
            "source_root": source_root,
            "course_rows": len(course_rows),
            "curriculum_rows": len(curriculum_rows),
            "curriculum_course_rows": len(curri_course_rows),
            "requirement_rows": len(requirement_rows),
            "unresolved_requisite_rows": len(unresolved_reqs),
            "course_conflict_rows": len(course_conflicts),
        },
    )


def parse_args() -> argparse.Namespace:
    """Parse CLI options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    """Run the extraction CLI."""
    args = parse_args()
    extract(args.source_root, args.output_dir.expanduser().resolve())
    print(f"wrote tucurricula import files to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
