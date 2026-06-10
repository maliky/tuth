"""Small tabular IO helpers for source-truth reports."""

from __future__ import annotations

import csv
import hashlib
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

from app.shared.file_utils import read_text_file

RowT: TypeAlias = dict[str, str]
RowsT: TypeAlias = Iterable[RowT]
HeadersT: TypeAlias = Sequence[str]


@dataclass(frozen=True)
class FileProfileT:
    """Observed shape and identity of one tabular source file."""

    path: Path
    actual_rows: int
    headers: tuple[str, ...]
    sha256: str
    size_bytes: int


def safe_cell(value: object) -> str:
    """Return a stable string cell for TSV/SQLite payloads."""
    if value is None:
        return ""
    return str(value).replace("\r\n", "\n").replace("\r", "\n").strip()


def normalize_header(value: object) -> str:
    """Normalize a source header without losing its readable spelling."""
    return safe_cell(value).strip().strip('"')


def ensure_csv_field_limit() -> None:
    """Raise CSV field limit for large legacy grade/comment fields."""
    try:
        csv.field_size_limit(sys.maxsize)
    except OverflowError:
        csv.field_size_limit(10_000_000)


def detect_delimiter(text: str) -> str:
    """Return tab when the header is tabular TSV, otherwise comma."""
    header = text.partition("\n")[0] if text else ""
    return "\t" if "\t" in header else ","


def read_rows(path: Path, *, delimiter: str | None = None) -> list[RowT]:
    """Read a CSV/TSV file into dictionaries with normalized headers."""
    ensure_csv_field_limit()
    if not path.exists() or path.stat().st_size == 0:
        return []
    text = read_text_file(path)
    if not text.strip():
        return []
    lines = text.splitlines()
    reader = csv.DictReader(lines, delimiter=delimiter or detect_delimiter(text))
    headers = [normalize_header(header) for header in (reader.fieldnames or [])]
    if not any(headers):
        return []
    normalized_keys: dict[str, str] = {}
    for key in reader.fieldnames or []:
        normalized_key = normalize_header(key)
        if normalized_key:
            normalized_keys[key] = normalized_key
    rows: list[RowT] = []
    for raw in reader:
        row: RowT = {}
        for key, value in raw.items():
            normalized_key = normalized_keys.get(key, "")
            if normalized_key:
                row[normalized_key] = safe_cell(value)
        rows.append(row)
    return rows


def profile_file(path: Path) -> FileProfileT:
    """Return file shape and hash without retaining row data."""
    ensure_csv_field_limit()
    raw = path.read_bytes() if path.exists() else b""
    sha256 = hashlib.sha256(raw).hexdigest() if raw else ""
    if not path.exists() or not raw.strip():
        return FileProfileT(path, 0, (), sha256, len(raw))
    text = read_text_file(path)
    if not text.strip():
        return FileProfileT(path, 0, (), sha256, len(raw))
    reader = csv.reader(text.splitlines(), delimiter=detect_delimiter(text))
    headers = tuple(
        header
        for header in (normalize_header(cell) for cell in next(reader, []))
        if header
    )
    row_count = sum(1 for _ in reader) if headers else 0
    return FileProfileT(path, row_count, headers, sha256, len(raw))


def write_tsv(path: Path, headers: HeadersT, rows: RowsT) -> int:
    """Write rows as LF-terminated TSV and return the row count."""
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(headers),
            delimiter="\t",
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {header: safe_cell(row.get(header, "")) for header in headers}
            )
            count += 1
    return count
