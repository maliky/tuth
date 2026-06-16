"""Build canonical report rows and import-ready TSV bundles."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path
from typing import TypeAlias

from app.shared.source_truth.college_codes import (
    canonical_college_code,
    canonicalize_college_fields,
)
from app.shared.source_truth.fuzzy import course_key
from app.shared.source_truth.io import RowT, write_tsv

RowsT: TypeAlias = list[RowT]
OutputCountsT: TypeAlias = dict[str, int]

MAX_CURRICULUM_CODE_LEN = 40
COURSE_HEADERS = (
    "course_dept",
    "course_no",
    "college_code",
    "course_title",
    "credit_hours",
    "description",
    "prerequisites",
)
CURRICULUM_HEADERS = (
    "curriculum",
    "long_name",
    "college_code",
    "status",
    "is_active",
    "list_courses",
)
CURRICULUM_COURSE_HEADERS = (
    "curriculum",
    "course_dept",
    "course_no",
    "credit_hours",
    "year_number",
    "semester_number",
    "level_number",
    "required_group_number",
    "min_validated_credits",
)


def build_canonical_courses(primary_rows: RowsT, historical_rows: RowsT) -> RowsT:
    """Return primary revised courses plus distinct historical-only rows."""
    rows: RowsT = []
    seen_keys: set[str] = set()
    for row in primary_rows:
        normalized = _course_output(row, "revised_catalog")
        rows.append(normalized)
        seen_keys.add(_course_identity(row))
    for row in historical_rows:
        identity = _course_identity(row)
        if not identity or identity in seen_keys:
            continue
        rows.append(_course_output(row, "historical_only"))
        seen_keys.add(identity)
    return rows


def build_canonical_curricula(primary_rows: RowsT, historical_rows: RowsT) -> RowsT:
    """Return revised curricula plus distinct historical-only curricula."""
    rows: RowsT = []
    seen_keys: set[str] = set()
    for row in primary_rows:
        rows.append(_curriculum_output(row, "revised_catalog"))
        seen_keys.add(_curriculum_identity(row))
    for row in historical_rows:
        identity = _curriculum_identity(row)
        if not identity or identity in seen_keys:
            continue
        rows.append(_curriculum_output(row, "historical_only"))
        seen_keys.add(identity)
    return rows


def build_canonical_curriculum_courses(
    primary_rows: RowsT, historical_rows: RowsT
) -> RowsT:
    """Return revised programmed courses plus historical-only programmed rows."""
    rows: RowsT = []
    seen_keys: set[str] = set()
    for row in primary_rows:
        rows.append(_curriculum_course_output(row, "revised_catalog"))
        seen_keys.add(_curriculum_course_identity(row))
    for row in historical_rows:
        identity = _curriculum_course_identity(row)
        if not identity or identity in seen_keys:
            continue
        rows.append(_curriculum_course_output(row, "historical_only"))
        seen_keys.add(identity)
    return rows


def write_import_ready_bundle(
    output_dir: Path,
    *,
    courses: RowsT,
    curricula: RowsT,
    curriculum_courses: RowsT,
    requirements: RowsT,
    students: RowsT,
    grades: RowsT,
    registrations: RowsT,
    semester_enrollments: RowsT,
    payments: RowsT,
) -> OutputCountsT:
    """Write Django-import-compatible TSV files."""
    import_dir = output_dir / "import_ready"
    counts: OutputCountsT = {}
    counts["import_ready/academic_course.tsv"] = write_tsv(
        import_dir / "academic_course.tsv", COURSE_HEADERS, courses
    )
    counts["import_ready/academic_curriculum.tsv"] = write_tsv(
        import_dir / "academic_curriculum.tsv", CURRICULUM_HEADERS, curricula
    )
    counts["import_ready/academic_curriculum_course.tsv"] = write_tsv(
        import_dir / "academic_curriculum_course.tsv",
        CURRICULUM_COURSE_HEADERS,
        curriculum_courses,
    )
    counts["import_ready/academic_curriculum_requirement.tsv"] = _write_passthrough(
        import_dir / "academic_curriculum_requirement.tsv", requirements
    )
    counts["import_ready/people_full_student.tsv"] = _write_passthrough(
        import_dir / "people_full_student.tsv", students
    )
    counts["import_ready/full_grades.tsv"] = _write_passthrough(
        import_dir / "full_grades.tsv", grades
    )
    counts["import_ready/registry_registration.tsv"] = _write_passthrough(
        import_dir / "registry_registration.tsv", registrations
    )
    counts["import_ready/registry_semester_enrollment.tsv"] = _write_passthrough(
        import_dir / "registry_semester_enrollment.tsv", semester_enrollments
    )
    counts["import_ready/finance_payments.tsv"] = _write_passthrough(
        import_dir / "finance_payments.tsv", payments
    )
    return counts


def _course_output(row: RowT, status: str) -> RowT:
    """Return one canonical/import-ready course row."""
    return {
        "course_dept": row.get("course_dept", ""),
        "course_no": row.get("course_no", ""),
        "college_code": canonical_college_code(row.get("college_code", "")),
        "course_title": row.get("course_title", ""),
        "credit_hours": row.get("credit_hours", ""),
        "description": row.get("description", ""),
        "prerequisites": row.get("prerequisites", ""),
        "canonical_status": status,
        "source_name": row.get("source_name", ""),
        "source_path": row.get("source_path", ""),
    }


def _curriculum_output(row: RowT, status: str) -> RowT:
    """Return one canonical/import-ready curriculum row."""
    curriculum = row.get("curriculum", "")
    return {
        "curriculum": _curriculum_code(row),
        "long_name": row.get("long_name", curriculum) or curriculum,
        "college_code": canonical_college_code(row.get("college_code", "")),
        "status": "approved" if status == "revised_catalog" else "historical",
        "is_active": "true" if status == "revised_catalog" else "false",
        "list_courses": row.get("list_courses", ""),
        "canonical_status": status,
        "source_name": row.get("source_name", ""),
        "source_path": row.get("source_path", ""),
    }


def _curriculum_course_output(row: RowT, status: str) -> RowT:
    """Return one canonical/import-ready curriculum-course row."""
    return {
        "curriculum": _curriculum_code(row),
        "course_dept": row.get("course_dept", ""),
        "course_no": row.get("course_no", ""),
        "credit_hours": row.get("credit_hours", "") or "3",
        "year_number": row.get("year_number", "") or "99",
        "semester_number": row.get("semester_number", "") or "0",
        "level_number": row.get("level_number", "") or "99",
        "required_group_number": row.get("required_group_number", "") or "0",
        "min_validated_credits": row.get("min_validated_credits", "") or "0",
        "canonical_status": status,
        "source_name": row.get("source_name", ""),
        "source_path": row.get("source_path", ""),
    }


def _write_passthrough(path: Path, rows: RowsT) -> int:
    """Write rows using their own columns minus provenance extras."""
    rows = [canonicalize_college_fields(row) for row in rows]
    headers = _passthrough_headers(rows)
    if not headers:
        headers = ("empty",)
        rows = []
    return write_tsv(path, headers, rows)


def _passthrough_headers(rows: RowsT) -> tuple[str, ...]:
    """Return stable headers for passthrough source rows."""
    blocked = {"source_name", "source_path"}
    seen: list[str] = []
    for row in rows:
        for key in row:
            if key in blocked or key in seen:
                continue
            seen.append(key)
    return tuple(seen)


def _course_identity(row: RowT) -> str:
    """Return import identity for a course row."""
    return course_key(row.get("course_dept"), row.get("course_no"))


def _curriculum_identity(row: RowT) -> str:
    """Return import identity for a curriculum row."""
    return "".join(ch for ch in row.get("curriculum", "").upper() if ch.isalnum())


def _curriculum_course_identity(row: RowT) -> str:
    """Return import identity for a curriculum-course row."""
    return f"{_curriculum_identity(row)}|{_course_identity(row)}"


def _curriculum_code(row: RowT) -> str:
    """Return a short import-safe curriculum code while preserving long_name."""
    raw_value = row.get("curriculum", "").strip()
    if len(raw_value) <= MAX_CURRICULUM_CODE_LEN:
        return raw_value
    compact = row.get("curriculum_key", "").strip() or _compact_token(raw_value)
    return _clamp_curriculum_code(compact or raw_value)


def _compact_token(value: str) -> str:
    """Collapse a verbose program label into an uppercase code-like token."""
    return "".join(ch for ch in value.upper() if ch.isalnum())


def _clamp_curriculum_code(value: str) -> str:
    """Clamp curriculum codes with a deterministic suffix when still too long."""
    if len(value) <= MAX_CURRICULUM_CODE_LEN:
        return value
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:6].upper()
    prefix_len = MAX_CURRICULUM_CODE_LEN - len(digest) - 1
    return f"{value[:prefix_len]}_{digest}"
