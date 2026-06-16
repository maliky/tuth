"""Curriculum matching helpers for SmartSchool-to-revised catalog migration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from app.academics.choices import LEGACY_CURRICULUM_MAP
from app.shared.fuzzy_matching import seq_similarity_score
from app.shared.source_truth.fuzzy import title_similarity
from app.shared.source_truth.io import RowT

RowsT: TypeAlias = list[RowT]
CurriculumMatchMapT: TypeAlias = dict[str, "CurriculumMatchT"]

REVISED_CURRICULUM_CODE_BY_LEGACY: dict[str, str] = {
    "BA - 2ndEd/Biology": "EDRCE-SEDU-BIOL",
    "BA - 2ndEd/Chemistry": "EDRCE-SEDU-CHEM",
    "BA - 2ndEd/Eng Lit": "EDRCE-SEDU-EDEN",
    "BA - 2ndEd/History": "EDRCE-SEDU-HIST",
    "BA - 2ndEd/Math": "EDRCE-SEDU-MATH",
    "BA - Early Child Dev": "EDRCE-ECED",
    "BA - Guidance Counseling": "EDRCE-GCED",
    "BA - Primary Ed": "EDRCE-PEDU",
    "BBA - Accounting": "CBA-ACCT",
    "BBA - Banking & Finance": "CBA-BFIN",
    "BBA - Management": "CBA-BUSA",
    "BPA - Management": "CBA-PADM",
    "BS - Biology": "CAS-BIOL",
    "BS - Chemistry": "CAS-CHEM",
    "BS - Civil Eng": "CET-CIVI",
    "BS - Computer Sci": "CET-CSEN",
    "BS - Economics": "CBA-ECON",
    "BS - Elec Eng": "CET-ELEC",
    "BS - Mech Eng": "CET-MECH",
    "BS - Midwifery": "CHS-MIDW",
    "BS - Nursing": "CHS-NURS",
    "BS - Public Health": "CHS-PUBH",
}


@dataclass(frozen=True)
class CurriculumMatchT:
    """One resolved revised-curriculum match."""

    target_curriculum: str
    target_long_name: str
    score: float
    method: str


def standardize_legacy_curriculum_label(label: str) -> str:
    """Return the canonical legacy label used before matching revised curricula."""
    value = label.strip()
    return LEGACY_CURRICULUM_MAP.get(value, value)


def curriculum_match_key(label: str) -> str:
    """Return a stable comparison key for curriculum labels."""
    return "".join(ch for ch in label.upper() if ch.isalnum())


def build_curriculum_match_map(
    source_rows: RowsT, target_rows: RowsT, *, fuzzy_threshold: float = 0.88
) -> tuple[CurriculumMatchMapT, RowsT]:
    """Return deterministic/fuzzy source-to-revised curriculum matches."""
    target_by_code, target_by_label = _target_indexes(target_rows)
    matches: CurriculumMatchMapT = {}
    report_rows: RowsT = []
    seen: set[str] = set()
    for source in source_rows:
        source_label = source.get("long_name") or source.get("curriculum", "")
        if not source_label:
            continue
        source_key = curriculum_match_key(source_label)
        if source_key in seen:
            continue
        seen.add(source_key)
        standardized = standardize_legacy_curriculum_label(source_label)
        match = _resolve_match(
            source_label,
            standardized,
            target_rows,
            target_by_code,
            target_by_label,
            fuzzy_threshold=fuzzy_threshold,
        )
        if match is not None:
            matches[source_key] = match
            matches[curriculum_match_key(standardized)] = match
        report_rows.append(_report_row(source_label, standardized, match))
    return matches, report_rows


def apply_curriculum_matches_to_students(
    students: RowsT, matches: CurriculumMatchMapT
) -> tuple[RowsT, RowsT]:
    """Set matched revised curricula on students and return review rows."""
    mapped_students: RowsT = []
    report_rows: RowsT = []
    for row in students:
        student = dict(row)
        source_label = (
            student.get("legacy_curriculum")
            or student.get("curriculum")
            or student.get("bio_EnrollmentType")
            or ""
        )
        standardized = standardize_legacy_curriculum_label(source_label)
        match = _lookup_match(matches, source_label) or _lookup_match(
            matches, standardized
        )
        target = standardized
        method = "legacy_fallback"
        score = "0.000"
        if match is not None:
            target = match.target_curriculum
            method = match.method
            score = f"{match.score:.3f}"
        student["curriculum"] = target
        student["legacy_curriculum"] = source_label
        student["curriculum_match_method"] = method
        mapped_students.append(student)
        report_rows.append(
            {
                "student_id": student.get("student_id", ""),
                "student_name": student.get("long_name", "")
                or student.get("student_name", ""),
                "source_curriculum": source_label,
                "standardized_curriculum": standardized,
                "target_curriculum": target,
                "match_method": method,
                "score": score,
            }
        )
    return mapped_students, report_rows


def _target_indexes(target_rows: RowsT) -> tuple[dict[str, RowT], dict[str, RowT]]:
    """Return revised curriculum indexes by code and label."""
    by_code: dict[str, RowT] = {}
    by_label: dict[str, RowT] = {}
    for target in target_rows:
        code = target.get("curriculum", "")
        label = target.get("long_name", "")
        if code:
            by_code[curriculum_match_key(code)] = target
        if label:
            by_label[curriculum_match_key(label)] = target
    return by_code, by_label


def _resolve_match(
    source_label: str,
    standardized: str,
    target_rows: RowsT,
    target_by_code: dict[str, RowT],
    target_by_label: dict[str, RowT],
    *,
    fuzzy_threshold: float,
) -> CurriculumMatchT | None:
    """Resolve one source label to a revised curriculum when safe."""
    exact = _exact_target(source_label, target_by_code, target_by_label) or _exact_target(
        standardized, target_by_code, target_by_label
    )
    if exact is not None:
        return _match_from_target(exact, 1.0, "exact")
    mapped_code = REVISED_CURRICULUM_CODE_BY_LEGACY.get(standardized, "")
    mapped = target_by_code.get(curriculum_match_key(mapped_code))
    if mapped is not None:
        return _match_from_target(mapped, 1.0, "legacy_map")
    fuzzy_target, score = _best_fuzzy_target(standardized, target_rows)
    if fuzzy_target is not None and score >= fuzzy_threshold:
        return _match_from_target(fuzzy_target, score, "fuzzy_high_confidence")
    return None


def _exact_target(
    label: str, target_by_code: dict[str, RowT], target_by_label: dict[str, RowT]
) -> RowT | None:
    """Return an exact revised target by code or title."""
    key = curriculum_match_key(label)
    return target_by_code.get(key) or target_by_label.get(key)


def _best_fuzzy_target(label: str, target_rows: RowsT) -> tuple[RowT | None, float]:
    """Return the best revised target and score for a label."""
    best: tuple[RowT | None, float] = (None, 0.0)
    for target in target_rows:
        target_label = target.get("long_name") or target.get("curriculum", "")
        score = max(
            seq_similarity_score(label.lower(), target_label.lower()),
            title_similarity(label, target_label),
        )
        if score > best[1]:
            best = (target, score)
    return best


def _match_from_target(target: RowT, score: float, method: str) -> CurriculumMatchT:
    """Build a typed match from a revised target row."""
    return CurriculumMatchT(
        target_curriculum=target.get("curriculum", ""),
        target_long_name=target.get("long_name", ""),
        score=score,
        method=method,
    )


def _lookup_match(
    matches: CurriculumMatchMapT, source_label: str
) -> CurriculumMatchT | None:
    """Return a curriculum match by raw or canonical label."""
    return matches.get(curriculum_match_key(source_label))


def _report_row(
    source_label: str, standardized: str, match: CurriculumMatchT | None
) -> RowT:
    """Build one review row for curriculum matching."""
    if match is None:
        return {
            "source_curriculum": source_label,
            "source_long_name": standardized,
            "candidate_rank": "1",
            "target_curriculum": "",
            "target_long_name": "",
            "score": "0.000",
            "recommendation": "legacy_fallback",
        }
    return {
        "source_curriculum": source_label,
        "source_long_name": standardized,
        "candidate_rank": "1",
        "target_curriculum": match.target_curriculum,
        "target_long_name": match.target_long_name,
        "score": f"{match.score:.3f}",
        "recommendation": match.method,
    }


__all__ = [
    "CurriculumMatchMapT",
    "CurriculumMatchT",
    "apply_curriculum_matches_to_students",
    "build_curriculum_match_map",
    "curriculum_match_key",
    "standardize_legacy_curriculum_label",
]
