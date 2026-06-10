"""Advisory curriculum-name candidates for later student-data remapping."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path
from typing import TypeAlias

from app.academics.current_usage import CurrentUsageT, iter_current_curriculum_rows
from app.academics.reconciliation_io import RowT, normalize_token, read_tsv
from app.shared.fuzzy_matching import seq_similarity_score

ScoredRowT: TypeAlias = tuple[float, RowT]

DROP_WORDS = {
    "A",
    "AN",
    "AND",
    "ART",
    "ARTS",
    "ASSOCIATE",
    "BACHELOR",
    "BUSINESS",
    "DEGREE",
    "IN",
    "OF",
    "PROGRAM",
    "SCIENCE",
    "THE",
}


def _program_token(*values: str) -> str:
    """Return a comparable token for program/curriculum names."""
    words = re.findall(r"[A-Z0-9]+", " ".join(values).upper())
    return " ".join(word for word in words if word not in DROP_WORDS)


def _score(current_row: RowT, org_row: RowT) -> float:
    """Return a blended similarity score between current and org curricula."""
    key_score = seq_similarity_score(
        normalize_token(current_row.get("curriculum")),
        normalize_token(org_row.get("curriculum")),
    )
    name_score = seq_similarity_score(
        _program_token(
            current_row.get("curriculum", ""), current_row.get("long_name", "")
        ),
        _program_token(org_row.get("curriculum", ""), org_row.get("long_name", "")),
    )
    return max(key_score, name_score)


def _recommendation(score: float) -> str:
    """Classify mapping confidence without authorizing automatic remap."""
    if score >= 0.85:
        return "strong_candidate_review"
    if score >= 0.65:
        return "possible_candidate_review"
    return "weak_candidate_review"


def _top_candidates(
    current_row: RowT, org_rows: Iterable[RowT], *, limit: int
) -> list[ScoredRowT]:
    """Return top org curriculum candidates for one current curriculum."""
    scored = [(_score(current_row, org_row), org_row) for org_row in org_rows]
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[:limit]


def build_curriculum_mapping_candidates(
    usage: CurrentUsageT,
    import_dir: Path,
    *,
    limit: int = 3,
) -> list[RowT]:
    """Return advisory current-curriculum to org-curriculum candidates."""
    org_rows = read_tsv(import_dir / "academic_curriculum.tsv")
    rows: list[RowT] = []
    current_rows = list(iter_current_curriculum_rows(usage))
    for current_row in current_rows:
        for rank, (score, org_row) in enumerate(
            _top_candidates(current_row, org_rows, limit=limit), start=1
        ):
            rows.append(
                {
                    "current_curriculum_id": current_row.get("curriculum_id", ""),
                    "current_curriculum": current_row.get("curriculum", ""),
                    "current_long_name": current_row.get("long_name", ""),
                    "usage_total": current_row.get("usage_total", "0"),
                    "candidate_rank": str(rank),
                    "org_curriculum": org_row.get("curriculum", ""),
                    "org_long_name": org_row.get("long_name", ""),
                    "similarity": f"{score:.3f}",
                    "recommendation": _recommendation(score),
                }
            )
    return rows
