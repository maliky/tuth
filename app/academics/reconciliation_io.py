"""Small TSV and key-normalization helpers for catalog reconciliation."""

from __future__ import annotations

import csv
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import TypeAlias

from app.shared.course_wrangling import normalize_token as shared_normalize_token

RowT: TypeAlias = dict[str, str]
RowsT: TypeAlias = Iterable[RowT]
HeadersT: TypeAlias = Sequence[str]


def as_cell(value: object) -> str:
    """Return a stable TSV cell representation for Django/export values."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def read_tsv(path: Path) -> list[RowT]:
    """Read a TSV file into dictionaries."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle, delimiter="\t")]


def write_tsv(path: Path, headers: HeadersT, rows: RowsT) -> int:
    """Write rows as TSV and return the number of written data rows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(headers),
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({header: row.get(header, "") for header in headers})
            count += 1
    return count


def normalize_token(value: str | None) -> str:
    """Return an uppercase alphanumeric token for deterministic comparison."""
    return shared_normalize_token(value)


def course_key(department_code: str | None, course_no: str | None) -> str:
    """Return the normalized course identity used across org and TUSIS rows."""
    return f"{normalize_token(department_code)}{normalize_token(course_no)}"


def split_course_key(raw_key: str | None) -> str:
    """Normalize a visible course key that already contains dept+number."""
    return normalize_token(raw_key)
