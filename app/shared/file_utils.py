"""Shared helpers for reading local files used by import commands."""

from __future__ import annotations

from pathlib import Path


def read_text_file(path: Path) -> str:
    """Return file contents, handling UTF-8/UTF-16 BOMs gracefully."""
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-16")


def guess_tabular_format(text: str) -> str:
    """Detect whether content is CSV or TSV based on the header row."""
    header = text.splitlines()[0] if text else ""
    return "tsv" if "\t" in header else "csv"
