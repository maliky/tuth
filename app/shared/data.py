"""Utility helpers to load split CSV dumps bundled with the project."""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from django.conf import settings

DEFAULT_REGISTRATION_FILES = (
    "Seed_data/Trimed/registry_registration.csv",
    "Seed_data/Trimed/registry_registration.head.csv",
)


def _candidate_paths(source_path: str | Path | None) -> Iterable[Path]:
    """Yield candidate paths for the legacy registration CSV."""
    bases: list[str | Path] = []
    if source_path:
        bases.append(source_path)

    env_override = getattr(settings, "TUSIS_LEGACY_REGISTRATIONS", None)
    if env_override:
        bases.append(env_override)

    bases.extend(DEFAULT_REGISTRATION_FILES)

    for candidate in bases:
        if candidate is None:
            continue
        path = Path(candidate).expanduser()
        if not path.is_absolute():
            path = Path(settings.BASE_DIR) / path
        yield path


def _read_rows(path: Path) -> tuple[dict[str, str], ...]:
    """Read the CSV file using utf-8-sig to absorb BOM artefacts."""
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: list[dict[str, str]] = []
        for raw in reader:
            cleaned = {
                (key or "").strip(): (value or "").strip()
                for key, value in (raw or {}).items()
            }
            rows.append(cleaned)
    return tuple(rows)


@lru_cache(maxsize=4)
def legacy_registration_rows(source_path: str | Path | None = None) -> tuple[dict[str, str], ...]:
    """Return cached rows from the trimmed registry_registration CSV if present."""
    for path in _candidate_paths(source_path):
        if path.exists():
            return _read_rows(path)
    return tuple()
