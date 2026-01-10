"""Shared helpers for reading local files used by import commands."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable


def read_text_file(path: Path) -> str:
    """Read a text file while handling UTF-8/UTF-16 BOMs.

    Args:
        path: File path to read.

    Returns:
        File contents as a string.
    """
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-16")


def guess_tabular_format(text: str) -> str:
    """Detect whether content is CSV or TSV based on the header row.

    Args:
        text: Tabular content to inspect.

    Returns:
        "tsv" when the header contains tabs, otherwise "csv".

    Examples:
        A header containing tabs yields "tsv".
    """
    header = text.splitlines()[0] if text else ""
    return "tsv" if "\t" in header else "csv"


def iter_migration_files(project_root: Path) -> Iterable[Path]:
    """Yield migration files from app migrations folders.

    Args:
        project_root: Project root to search within.

    Yields:
        File locations for migration .py and .pyc files, excluding __init__.py.
    """
    # Any app: <app>/migrations/*.py (except __init__.py) and *.pyc
    for mig_dir in project_root.rglob("migrations"):
        if not mig_dir.is_dir():
            continue
        for p in mig_dir.iterdir():
            if p.name == "__init__.py":
                continue
            if p.suffix in {".py", ".pyc"}:
                yield p
