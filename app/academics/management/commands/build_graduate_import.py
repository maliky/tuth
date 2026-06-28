"""Build TUSIS graduate curriculum import TSVs from the maintained Org source."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, TypeAlias

from django.core.management.base import BaseCommand, CommandError, CommandParser

from app.academics.choices import AcademicCareer
from app.academics.models import Course

DEFAULT_SOURCE = Path("../../tucurricula/tu_graduate_curricula_2026.org")
DEFAULT_OUTPUT_DIR = Path("data/graduate_import")
COURSE_RE = re.compile(r"^(?P<dept>[A-Z]{3,5})\s*(?P<number>\d{3})$")
MACRO_RE = re.compile(
    r"\\TUCCrsDescDef(?:\[(?P<prereq>[^\]]*)\])?(?:\[(?P<coreq>[^\]]*)\])?"
)
PREREQ_COURSE_RE = re.compile(r"\b([A-Z]{3,5})\s*(\d{3})\b")
PROGRAM_HEADER_RE = re.compile(
    r"\\TUCNewGlo\{(?P<slug>grad-[^{}]+)\}\{(?P<title>[^{}]+)\}"
)

CourseCodeT: TypeAlias = tuple[str, str]


@dataclass(frozen=True)
class ProgramSpec:
    """Configured import identity for one graduate source program."""

    slug: str
    title: str
    college_code: str
    curriculum_code: str


@dataclass(frozen=True)
class CourseRow:
    """One course placement extracted from a graduate curriculum table."""

    slug: str
    dept: str
    number: str
    title: str
    credits: int
    year_number: int
    semester_number: int
    level_number: int
    is_required: bool
    is_elective: bool
    required_group_number: int

    @property
    def code(self) -> str:
        """Return compact course key."""
        return f"{self.dept}{self.number}"


@dataclass(frozen=True)
class ElectivePlaceholder:
    """Elective placeholder location from a curriculum plan table."""

    slug: str
    title: str
    credits: int
    year_number: int
    semester_number: int
    level_number: int
    required_group_number: int


@dataclass(frozen=True)
class CourseDescription:
    """Course catalog description extracted from a TUCurricula macro."""

    dept: str
    number: str
    title: str
    credits: int | None
    description: str
    prerequisites: tuple[CourseCodeT, ...]
    corequisites: tuple[CourseCodeT, ...]

    @property
    def code(self) -> str:
        """Return compact course key."""
        return f"{self.dept}{self.number}"


@dataclass(frozen=True)
class ProgramBundle:
    """Extracted table and description rows for one graduate program."""

    spec: ProgramSpec
    courses: tuple[CourseRow, ...]
    placeholders: tuple[ElectivePlaceholder, ...]
    descriptions: dict[str, CourseDescription]

    @property
    def slug(self) -> str:
        """Return the source slug."""
        return self.spec.slug

    @property
    def title(self) -> str:
        """Return the source program title."""
        return self.spec.title


class Command(BaseCommand):
    """Generate graduate import TSVs and audit reports."""

    help = "Build graduate import TSVs from tu_graduate_curricula_2026.org."

    def add_arguments(self, parser: CommandParser) -> None:
        """Register command options."""
        parser.add_argument("--source", default=str(DEFAULT_SOURCE))
        parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))

    def handle(self, *args: object, **options: object) -> None:
        """Build import files from all graduate programs in the source."""
        source = Path(str(options["source"]))
        output_dir = Path(str(options["output_dir"]))
        if not source.exists():
            raise CommandError(f"Graduate source not found: {source}")

        text = source.read_text(encoding="utf-8")
        specs = _program_specs(text)
        descriptions = _global_description_map(text)
        bundles = [_extract_program(text, spec, descriptions) for spec in specs]
        valid, rejected, conflicts, unresolved = _audit_bundles(bundles)
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_import_files(output_dir, valid, source)
        _write_report_files(output_dir, rejected, conflicts, unresolved)
        _write_summary(output_dir, source, valid, rejected, conflicts, unresolved)
        self.stdout.write(
            self.style.SUCCESS(
                f"Graduate bundle written to {output_dir}: "
                f"{len(valid)} valid, {len(rejected)} rejected."
            )
        )


def _program_specs(text: str) -> tuple[ProgramSpec, ...]:
    """Return graduate program specs from source header declarations."""
    specs: list[ProgramSpec] = []
    for match in PROGRAM_HEADER_RE.finditer(text):
        slug = match.group("slug")
        specs.append(
            ProgramSpec(
                slug=slug,
                title=_clean_title(match.group("title")),
                college_code=_college_code_for_slug(slug),
                curriculum_code=_curriculum_code_for_slug(slug),
            )
        )
    if not specs:
        raise CommandError("No graduate program declarations found in source.")
    return tuple(specs)


def _college_code_for_slug(slug: str) -> str:
    """Return the disciplinary college that owns a graduate program slug."""
    if slug in {"grad-educ-el", "grad-educ-ci", "grad-pgde"}:
        return "EDRCE"
    if slug in {"grad-mbam", "grad-mbaf", "grad-pgba"}:
        return "CBA"
    if slug in {"grad-msgh", "grad-pgph"}:
        return "CHS"
    if slug in {"grad-meng", "grad-mscm"}:
        return "CET"
    return "CAS"


def _curriculum_code_for_slug(slug: str) -> str:
    """Return the TUSIS curriculum short code for a graduate source slug."""
    return f"GRAD-{slug.removeprefix('grad-').upper()}"


def _global_description_map(text: str) -> dict[str, CourseDescription]:
    """Return course descriptions from every graduate description block."""
    descriptions: dict[str, CourseDescription] = {}
    for line in text.splitlines():
        if "\\TUCCrsDescDef" not in line:
            continue
        parsed = _parse_description_macro(line)
        if parsed is not None:
            descriptions.setdefault(parsed.code, parsed)
    return descriptions


def _extract_program(
    text: str,
    spec: ProgramSpec,
    global_descriptions: dict[str, CourseDescription],
) -> ProgramBundle:
    """Extract curriculum rows and course descriptions for one source slug."""
    body = _section_text(text, spec.title)
    descriptions = {**global_descriptions, **_description_map(text, spec.slug)}
    return ProgramBundle(
        spec=spec,
        courses=tuple(_table_courses(spec.slug, body)),
        placeholders=tuple(_elective_placeholders(spec.slug, body)),
        descriptions=descriptions,
    )


def _section_text(text: str, title: str) -> str:
    """Return one second-level Org section body."""
    pattern = re.compile(rf"^##? {re.escape(title)}$", re.M)
    match = pattern.search(text)
    if match is None:
        # Generated Org uses `**` for program headings.
        pattern = re.compile(rf"^\*\* {re.escape(title)}$", re.M)
        match = pattern.search(text)
    if match is None:
        raise CommandError(f"Program heading not found: {title}")
    next_match = re.search(r"^\*\* ", text[match.end() :], re.M)
    end = match.end() + next_match.start() if next_match else len(text)
    return text[match.end() : end]


def _table_courses(slug: str, body: str) -> Iterable[CourseRow]:
    """Yield course rows from generated LaTeX curriculum tables."""
    table_re = re.compile(
        rf"\\TUCTblAnchor\{{tbl:{re.escape(slug)}-t(?P<table_no>\d+)\}}(?P<body>.*?)% END RECEIVE",
        re.S,
    )
    placeholders = list(_elective_placeholders(slug, body))
    elective_table_index = 0
    for table_match in table_re.finditer(body):
        table_no = int(table_match.group("table_no"))
        table_heading = _nearest_heading(body, table_match.start())
        is_elective_table = "elective" in table_heading.lower()
        elective_placement = (
            placeholders[min(elective_table_index, len(placeholders) - 1)]
            if is_elective_table and placeholders
            else None
        )
        if is_elective_table:
            elective_table_index += 1
        table_body = table_match.group("body")
        for raw_line in table_body.splitlines():
            line = raw_line.strip()
            if "&" not in line or line.startswith("\\") or line.startswith("%"):
                continue
            cells = [_clean_cell(cell) for cell in line.rstrip("\\").split("&")]
            if len(cells) >= 6:
                yield from _six_column_courses(slug, table_no, cells[:6])
            elif len(cells) >= 3:
                level_number = _three_column_level_number(table_no, table_heading)
                year_number, semester_number = _year_semester_from_level(level_number)
                course = _course_from_cells(
                    slug,
                    year_number,
                    semester_number,
                    level_number,
                    cells[0],
                    cells[1],
                    cells[2],
                    is_elective=is_elective_table,
                    required_group_number=(
                        elective_placement.required_group_number
                        if elective_placement is not None
                        else 0
                    ),
                )
                if course is not None:
                    if elective_placement is not None:
                        yield CourseRow(
                            slug=course.slug,
                            dept=course.dept,
                            number=course.number,
                            title=course.title,
                            credits=course.credits,
                            year_number=elective_placement.year_number,
                            semester_number=elective_placement.semester_number,
                            level_number=elective_placement.level_number,
                            is_required=False,
                            is_elective=True,
                            required_group_number=elective_placement.required_group_number,
                        )
                    else:
                        yield course


def _six_column_courses(
    slug: str,
    table_no: int,
    cells: list[str],
) -> Iterable[CourseRow]:
    """Yield left and right semester courses from a six-column table row."""
    left_level = (table_no - 1) * 2 + 1
    right_level = left_level + 1
    left = _course_from_cells(
        slug,
        *_year_semester_from_level(left_level),
        left_level,
        cells[0],
        cells[1],
        cells[2],
    )
    right = _course_from_cells(
        slug,
        *_year_semester_from_level(right_level),
        right_level,
        cells[3],
        cells[4],
        cells[5],
    )
    if left is not None:
        yield left
    if right is not None:
        yield right


def _course_from_cells(
    slug: str,
    year_number: int,
    semester_number: int,
    level_number: int,
    code: str,
    title: str,
    credits: str,
    *,
    is_elective: bool = False,
    required_group_number: int = 0,
) -> CourseRow | None:
    """Return a course row from visible table cells, skipping totals/placeholders."""
    visible_code = code.strip()
    if not visible_code or visible_code.lower().startswith(("total", "semester")):
        return None
    match = COURSE_RE.match(visible_code.replace(" ", ""))
    if match is None:
        return None
    credit_value = _int_or_none(credits)
    if credit_value is None:
        return None
    return CourseRow(
        slug=slug,
        dept=match.group("dept"),
        number=match.group("number"),
        title=_clean_title(title),
        credits=credit_value,
        year_number=year_number,
        semester_number=semester_number,
        level_number=level_number,
        is_required=not is_elective,
        is_elective=is_elective,
        required_group_number=required_group_number,
    )


def _nearest_heading(body: str, position: int) -> str:
    """Return the nearest Org heading above a table anchor."""
    prefix = body[:position]
    headings = re.findall(r"^\*{3,6}\s+(.+)$", prefix, flags=re.M)
    return _clean_title(headings[-1]) if headings else ""


def _three_column_level_number(table_no: int, heading: str) -> int:
    """Return level placement for a single-semester table."""
    heading_lower = heading.lower()
    if "semester two" in heading_lower or "semester ii" in heading_lower:
        return 2
    if "semester one" in heading_lower or "semester i" in heading_lower:
        return 1
    return max(table_no, 1)


def _year_semester_from_level(level_number: int) -> tuple[int, int]:
    """Return academic year and semester numbers from a sequential level."""
    return (level_number - 1) // 2 + 1, 1 if level_number % 2 else 2


def _elective_placeholders(slug: str, body: str) -> Iterable[ElectivePlaceholder]:
    """Yield elective placeholder rows that need mapped elective choices."""
    table_re = re.compile(
        rf"\\TUCTblAnchor\{{tbl:{re.escape(slug)}-t(?P<table_no>\d+)\}}(?P<body>.*?)% END RECEIVE",
        re.S,
    )
    group_number = 0
    for table_match in table_re.finditer(body):
        table_no = int(table_match.group("table_no"))
        table_heading = _nearest_heading(body, table_match.start())
        for raw_line in table_match.group("body").splitlines():
            line = raw_line.strip()
            if "&" not in line or line.startswith("\\") or line.startswith("%"):
                continue
            cells = [_clean_cell(cell) for cell in line.rstrip("\\").split("&")]
            cell_sets: list[tuple[int, str, str, str]]
            if len(cells) >= 6:
                left_level = (table_no - 1) * 2 + 1
                right_level = left_level + 1
                cell_sets = [
                    (left_level, cells[0], cells[1], cells[2]),
                    (right_level, cells[3], cells[4], cells[5]),
                ]
            elif len(cells) >= 3:
                level_number = _three_column_level_number(table_no, table_heading)
                cell_sets = [(level_number, cells[0], cells[1], cells[2])]
            else:
                cell_sets = []
            for level_number, code, title, credits in cell_sets:
                if "elective" not in code.lower():
                    continue
                credit_value = _int_or_none(credits)
                if credit_value is None:
                    continue
                group_number += 1
                year_number, semester_number = _year_semester_from_level(level_number)
                yield ElectivePlaceholder(
                    slug=slug,
                    title=_clean_title(code or title),
                    credits=credit_value,
                    year_number=year_number,
                    semester_number=semester_number,
                    level_number=level_number,
                    required_group_number=group_number,
                )


def _description_map(text: str, slug: str) -> dict[str, CourseDescription]:
    """Return course descriptions keyed by compact course key."""
    start_token = f"\\TUCSetCrsGloT{{{slug}}}"
    end_token = f"\\TUPrintCrsGlo{{{slug}}}"
    start = text.find(start_token)
    end = text.find(end_token, start)
    if start < 0 or end < 0:
        return {}
    block = text[start:end]
    descriptions: dict[str, CourseDescription] = {}
    for line in block.splitlines():
        if "\\TUCCrsDescDef" not in line:
            continue
        parsed = _parse_description_macro(line)
        if parsed is not None:
            descriptions[parsed.code] = parsed
    return descriptions


def _parse_description_macro(line: str) -> CourseDescription | None:
    """Parse one TUCCrsDescDef macro line into a description record."""
    match = MACRO_RE.search(line)
    if match is None:
        return None
    groups = _brace_groups(line[match.end() :])
    if len(groups) < 5:
        return None
    code_text = _clean_cell(groups[1])
    code_match = COURSE_RE.match(code_text.replace(" ", ""))
    if code_match is None:
        return None
    prereq_text = (match.group("prereq") or "").strip()
    prerequisites = tuple(
        (dept, number) for dept, number in PREREQ_COURSE_RE.findall(prereq_text)
    )
    coreq_text = (match.group("coreq") or "").strip()
    corequisites = tuple(
        (dept, number) for dept, number in PREREQ_COURSE_RE.findall(coreq_text)
    )
    return CourseDescription(
        dept=code_match.group("dept"),
        number=code_match.group("number"),
        title=_clean_title(groups[2]),
        credits=_int_or_none(groups[3]),
        description=_clean_title(groups[4]),
        prerequisites=prerequisites,
        corequisites=corequisites,
    )


def _brace_groups(text: str) -> list[str]:
    """Return top-level brace groups from a macro tail."""
    groups: list[str] = []
    depth = 0
    start: int | None = None
    for index, char in enumerate(text):
        if char == "{" and (index == 0 or text[index - 1] != "\\"):
            if depth == 0:
                start = index + 1
            depth += 1
        elif char == "}" and (index == 0 or text[index - 1] != "\\"):
            depth -= 1
            if depth == 0 and start is not None:
                groups.append(text[start:index])
                start = None
    return groups


def _audit_bundles(
    bundles: Iterable[ProgramBundle],
) -> tuple[
    list[ProgramBundle],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    """Split bundles into importable programs and audit reports."""
    valid: list[ProgramBundle] = []
    rejected: list[dict[str, str]] = []
    conflicts: list[dict[str, str]] = []
    unresolved: list[dict[str, str]] = []
    for bundle in bundles:
        reasons = _rejection_reasons(bundle)
        bundle_conflicts = _course_conflicts(bundle)
        bundle_unresolved = _unresolved_prereqs(bundle)
        if reasons or bundle_conflicts or bundle_unresolved:
            rejected.extend(reasons)
            conflicts.extend(bundle_conflicts)
            unresolved.extend(bundle_unresolved)
            if bundle_conflicts:
                rejected.append(
                    _reject(
                        bundle, "course_conflict", "Existing course metadata differs."
                    )
                )
            if bundle_unresolved:
                rejected.append(
                    _reject(
                        bundle,
                        "unresolved_prerequisite",
                        "Course-code prerequisite could not be resolved.",
                    )
                )
            continue
        valid.append(bundle)
    return valid, rejected, conflicts, unresolved


def _rejection_reasons(bundle: ProgramBundle) -> list[dict[str, str]]:
    """Return curriculum-level reject rows for source-table issues."""
    reasons: list[dict[str, str]] = []
    if not bundle.courses:
        reasons.append(
            _reject(bundle, "missing_curriculum_rows", "No course table rows found.")
        )
    reasons.extend(_missing_description_reasons(bundle))
    reasons.extend(_unresolved_elective_reasons(bundle))
    return reasons


def _missing_description_reasons(bundle: ProgramBundle) -> list[dict[str, str]]:
    """Return reject rows for courses missing catalog descriptions."""
    reasons: list[dict[str, str]] = []
    for course in bundle.courses:
        description = bundle.descriptions.get(course.code)
        if description is None or not description.description:
            reasons.append(
                _reject(
                    bundle,
                    "missing_course_description",
                    "Course has no graduate source description.",
                    course=course,
                )
            )
    return reasons


def _unresolved_elective_reasons(bundle: ProgramBundle) -> list[dict[str, str]]:
    """Return reject rows when source elective placeholders are not mapped."""
    elective_groups = {
        course.required_group_number
        for course in bundle.courses
        if course.is_elective and course.required_group_number
    }
    reasons: list[dict[str, str]] = []
    for placeholder in bundle.placeholders:
        if placeholder.required_group_number in elective_groups:
            continue
        reasons.append(
            _reject(
                bundle,
                "unresolved_elective_placeholder",
                (
                    f"{placeholder.title} at level {placeholder.level_number} "
                    "has no importable elective choice table."
                ),
            )
        )
    return reasons


def _course_conflicts(bundle: ProgramBundle) -> list[dict[str, str]]:
    """Return rows where existing catalog metadata conflicts with source data."""
    rows: list[dict[str, str]] = []
    college_code = bundle.spec.college_code
    for source in _unique_course_descriptions(bundle):
        existing = (
            Course.objects.filter(
                department__code=source.dept,
                department__college__code=college_code,
                number=source.number,
            )
            .select_related("department")
            .first()
        )
        if existing is None:
            continue
        title_conflict = bool(
            source.title and existing.title and existing.title != source.title
        )
        desc_conflict = bool(
            source.description
            and existing.description
            and existing.description.strip() != source.description.strip()
        )
        if title_conflict or desc_conflict:
            rows.append(
                {
                    "source_slug": bundle.slug,
                    "course_code": f"{source.dept} {source.number}",
                    "existing_title": existing.title or "",
                    "source_title": source.title,
                    "existing_description": existing.description or "",
                    "source_description": source.description,
                    "reason": "title_or_description_conflict",
                }
            )
    return rows


def _unresolved_prereqs(bundle: ProgramBundle) -> list[dict[str, str]]:
    """Return course-code prerequisites that are absent from source/current DB."""
    source_keys = {(course.dept, course.number) for course in bundle.courses}
    rows: list[dict[str, str]] = []
    for description in _unique_course_descriptions(bundle):
        for dept, number in (*description.prerequisites, *description.corequisites):
            if (dept, number) in source_keys:
                continue
            if Course.objects.filter(department__code=dept, number=number).exists():
                continue
            rows.append(
                {
                    "source_slug": bundle.slug,
                    "course_code": f"{description.dept} {description.number}",
                    "required_course_code": f"{dept} {number}",
                    "reason": "required course not found in source or DB",
                }
            )
    return rows


def _unique_course_descriptions(bundle: ProgramBundle) -> Iterable[CourseDescription]:
    """Yield one description/catalog source per table course."""
    seen: set[str] = set()
    for course in bundle.courses:
        if course.code in seen:
            continue
        seen.add(course.code)
        yield bundle.descriptions.get(
            course.code,
            CourseDescription(
                dept=course.dept,
                number=course.number,
                title=course.title,
                credits=course.credits,
                description="",
                prerequisites=(),
                corequisites=(),
            ),
        )


def _reject(
    bundle: ProgramBundle,
    code: str,
    detail: str,
    *,
    course: CourseRow | None = None,
) -> dict[str, str]:
    """Return one rejected-curriculum audit row."""
    return {
        "source_slug": bundle.slug,
        "curriculum": bundle.spec.curriculum_code,
        "course_code": f"{course.dept} {course.number}" if course else "",
        "reason": code,
        "detail": detail,
    }


def _write_import_files(
    output_dir: Path, bundles: list[ProgramBundle], source: Path
) -> None:
    """Write import_resources-compatible TSV files."""
    course_rows: list[dict[str, str]] = []
    curriculum_rows: list[dict[str, str]] = []
    curriculum_course_rows: list[dict[str, str]] = []
    requirement_rows: list[dict[str, str]] = []
    for bundle in bundles:
        college_code = bundle.spec.college_code
        curriculum = bundle.spec.curriculum_code
        curriculum_rows.append(
            {
                "college_code": college_code,
                "curriculum_college_code": college_code,
                "curriculum": curriculum,
                "long_name": bundle.title,
                "status": "approved",
                "is_active": "true",
                "academic_career": AcademicCareer.GRADUATE.value,
                "source_slug": bundle.slug,
            }
        )
        for description in _unique_course_descriptions(bundle):
            course_rows.append(
                {
                    "college_code": college_code,
                    "course_college_code": college_code,
                    "course_dept": description.dept,
                    "course_no": description.number,
                    "course_title": description.title,
                    "credit_hours": str(description.credits or ""),
                    "description": description.description,
                    "source_course_key": description.code,
                    "source_files": str(source),
                    "academic_career": AcademicCareer.GRADUATE.value,
                }
            )
        for course in bundle.courses:
            curriculum_course_rows.append(
                {
                    "college_code": college_code,
                    "curriculum_college_code": college_code,
                    "course_college_code": college_code,
                    "curriculum": curriculum,
                    "course_dept": course.dept,
                    "course_no": course.number,
                    "course_title": course.title,
                    "credit_hours": str(course.credits),
                    "year_number": str(course.year_number),
                    "semester_number": str(course.semester_number),
                    "level_number": str(course.level_number),
                    "required_group_number": str(course.required_group_number),
                    "min_validated_credits": "0",
                    "is_required": "true" if course.is_required else "false",
                    "is_elective": "true" if course.is_elective else "false",
                    "source_course_key": course.code,
                    "source_program": bundle.title,
                    "academic_career": AcademicCareer.GRADUATE.value,
                }
            )
        requirement_rows.extend(_requirement_rows(bundle, source))
    _write_tsv(output_dir / "academic_course.tsv", course_rows, COURSE_FIELDS)
    _write_tsv(output_dir / "academic_curriculum.tsv", curriculum_rows, CURRICULUM_FIELDS)
    _write_tsv(
        output_dir / "academic_curriculum_course.tsv",
        curriculum_course_rows,
        CURRICULUM_COURSE_FIELDS,
    )
    _write_tsv(
        output_dir / "academic_curriculum_requirement.tsv",
        requirement_rows,
        REQUIREMENT_FIELDS,
    )


def _requirement_rows(bundle: ProgramBundle, source: Path) -> list[dict[str, str]]:
    """Return grouped prerequisite rows for course-code prerequisites."""
    rows: list[dict[str, str]] = []
    college_code = bundle.spec.college_code
    curriculum = bundle.spec.curriculum_code
    source_courses = {course.code: course for course in bundle.courses}
    for description in _unique_course_descriptions(bundle):
        target = source_courses.get(description.code)
        if target is None:
            continue
        rows.extend(
            _requirement_kind_rows(
                source=source,
                college_code=college_code,
                curriculum=curriculum,
                target=target,
                requirement_kind="prereq_all",
                requirements=description.prerequisites,
            )
        )
        rows.extend(
            _requirement_kind_rows(
                source=source,
                college_code=college_code,
                curriculum=curriculum,
                target=target,
                requirement_kind="coreq_all",
                requirements=description.corequisites,
            )
        )
    return rows


def _requirement_kind_rows(
    *,
    source: Path,
    college_code: str,
    curriculum: str,
    target: CourseRow,
    requirement_kind: str,
    requirements: tuple[CourseCodeT, ...],
) -> list[dict[str, str]]:
    """Return import rows for one requirement group kind."""
    rows: list[dict[str, str]] = []
    for order, (dept, number) in enumerate(requirements, start=1):
        rows.append(
            {
                "college_code": college_code,
                "curriculum_college_code": college_code,
                "course_college_code": college_code,
                "curriculum": curriculum,
                "course_dept": target.dept,
                "course_no": target.number,
                "required_course_college_code": college_code,
                "required_course_dept": dept,
                "required_course_no": number,
                "requirement_kind": requirement_kind,
                "requirement_label": f"source {requirement_kind} {target.code}",
                "requirement_order": "1",
                "member_order": str(order),
                "source_file": str(source),
                "source_course_key": target.code,
                "raw_requisite": " ".join(f"{d} {n}" for d, n in requirements),
            }
        )
    return rows


def _write_report_files(
    output_dir: Path,
    rejected: list[dict[str, str]],
    conflicts: list[dict[str, str]],
    unresolved: list[dict[str, str]],
) -> None:
    """Write audit report TSV files."""
    _write_tsv(output_dir / "rejected_curricula.tsv", rejected, REJECT_FIELDS)
    _write_tsv(output_dir / "course_conflicts.tsv", conflicts, CONFLICT_FIELDS)
    _write_tsv(output_dir / "unresolved_requisites.tsv", unresolved, UNRESOLVED_FIELDS)


def _write_summary(
    output_dir: Path,
    source: Path,
    valid: list[ProgramBundle],
    rejected: list[dict[str, str]],
    conflicts: list[dict[str, str]],
    unresolved: list[dict[str, str]],
) -> None:
    """Write a compact human-readable build summary."""
    lines = [
        f"source: {source}",
        f"valid_curricula: {len(valid)}",
        f"rejected_rows: {len(rejected)}",
        f"course_conflicts: {len(conflicts)}",
        f"unresolved_requisites: {len(unresolved)}",
        "valid_slugs: " + ", ".join(bundle.slug for bundle in valid),
    ]
    (output_dir / "SUMMARY.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_tsv(path: Path, rows: list[dict[str, str]], fields: tuple[str, ...]) -> None:
    """Write rows to a TSV, preserving headers for empty reports."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def _clean_cell(value: str) -> str:
    """Return visible text from a LaTeX table cell."""
    text = value.strip()
    text = re.sub(r"\\truncate\{[^{}]*\}\{([^{}]*)\}", r"\1", text)
    text = text.replace(r"\&", "&").replace(r"\%", "%")
    text = re.sub(r"\\textbf\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\[A-Za-z]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _clean_title(value: str) -> str:
    """Normalize display text while preserving source words."""
    return _clean_cell(value).strip("{} ")


def _int_or_none(value: str) -> int | None:
    """Return the first integer in a string."""
    match = re.search(r"\d+", value or "")
    return int(match.group(0)) if match else None


COURSE_FIELDS = (
    "college_code",
    "course_college_code",
    "course_dept",
    "course_no",
    "course_title",
    "credit_hours",
    "description",
    "source_course_key",
    "source_files",
    "academic_career",
)
CURRICULUM_FIELDS = (
    "college_code",
    "curriculum_college_code",
    "curriculum",
    "long_name",
    "status",
    "is_active",
    "academic_career",
    "source_slug",
)
CURRICULUM_COURSE_FIELDS = (
    "college_code",
    "curriculum_college_code",
    "course_college_code",
    "curriculum",
    "course_dept",
    "course_no",
    "course_title",
    "credit_hours",
    "year_number",
    "semester_number",
    "level_number",
    "required_group_number",
    "min_validated_credits",
    "is_required",
    "is_elective",
    "source_course_key",
    "source_program",
    "academic_career",
)
REQUIREMENT_FIELDS = (
    "college_code",
    "curriculum_college_code",
    "course_college_code",
    "curriculum",
    "course_dept",
    "course_no",
    "required_course_college_code",
    "required_course_dept",
    "required_course_no",
    "requirement_kind",
    "requirement_label",
    "requirement_order",
    "member_order",
    "source_file",
    "source_course_key",
    "raw_requisite",
)
REJECT_FIELDS = ("source_slug", "curriculum", "course_code", "reason", "detail")
CONFLICT_FIELDS = (
    "source_slug",
    "course_code",
    "existing_title",
    "source_title",
    "existing_description",
    "source_description",
    "reason",
)
UNRESOLVED_FIELDS = ("source_slug", "course_code", "required_course_code", "reason")
